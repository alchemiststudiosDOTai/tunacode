"""Module: tunacode.core.agents.main

Main agent functionality.

Phase 4 migration note:

This module now consumes **tinyagent** events directly via ``agent.stream()``.
The legacy pydantic-ai node-based orchestrator is intentionally bypassed.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from tinyagent import Agent

from tunacode.constants import DEFAULT_CONTEXT_WINDOW
from tunacode.exceptions import ContextOverflowError, GlobalRequestTimeoutError, UserAbortError
from tunacode.types import (
    ModelName,
    NoticeCallback,
    StreamingCallback,
    ToolCallback,
    ToolResultCallback,
    ToolStartCallback,
    UsageMetrics,
)
from tunacode.utils.messaging import estimate_messages_tokens

from tunacode.core.compaction.controller import (
    CompactionStatusCallback,
    apply_compaction_messages,
    build_compaction_notice,
    get_or_create_compaction_controller,
)
from tunacode.core.compaction.types import CompactionOutcome
from tunacode.core.logging import get_logger
from tunacode.core.types import RuntimeState, StateManagerProtocol

from . import agent_components as ac

__all__ = [
    "process_request",
    "get_agent_tool",
]

DEFAULT_MAX_ITERATIONS: int = 15
REQUEST_ID_LENGTH: int = 8
MILLISECONDS_PER_SECOND: int = 1000

CONTEXT_OVERFLOW_PATTERNS: tuple[str, ...] = (
    "context_length_exceeded",
    "maximum context length",
)
CONTEXT_OVERFLOW_RETRY_NOTICE = "Context overflow detected. Compacting and retrying once..."
CONTEXT_OVERFLOW_FAILURE_NOTICE = (
    "Context is still too large after compaction. Use /compact or /clear and retry."
)


def _coerce_int(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        try:
            return int(stripped)
        except ValueError:
            return 0
    return 0


def _coerce_float(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0.0
        try:
            return float(stripped)
        except ValueError:
            return 0.0
    return 0.0


def _coerce_error_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def _is_context_overflow_error(error_text: str) -> bool:
    if not error_text:
        return False

    normalized_error = error_text.lower()
    return any(pattern in normalized_error for pattern in CONTEXT_OVERFLOW_PATTERNS)


USAGE_PROMPT_TOKEN_KEYS: tuple[str, ...] = (
    "prompt_tokens",
    "promptTokens",
    "input",
    "input_tokens",
    "inputTokens",
)
USAGE_COMPLETION_TOKEN_KEYS: tuple[str, ...] = (
    "completion_tokens",
    "completionTokens",
    "output",
    "output_tokens",
    "outputTokens",
)
USAGE_CACHE_READ_KEYS: tuple[str, ...] = (
    "cacheRead",
    "cache_read",
    "cache_read_input_tokens",
    "cacheReadInputTokens",
)
USAGE_PROMPT_DETAILS_KEYS: tuple[str, ...] = (
    "prompt_tokens_details",
    "promptTokensDetails",
)
USAGE_PROMPT_DETAILS_CACHED_KEYS: tuple[str, ...] = (
    "cached_tokens",
    "cachedTokens",
)
USAGE_COST_KEYS: tuple[str, ...] = ("cost", "total_cost", "totalCost")
USAGE_COST_TOTAL_KEYS: tuple[str, ...] = ("total", "total_cost", "totalCost")
USAGE_COST_INPUT_KEYS: tuple[str, ...] = ("input",)
USAGE_COST_OUTPUT_KEYS: tuple[str, ...] = ("output",)
USAGE_COST_CACHE_READ_KEYS: tuple[str, ...] = ("cache_read", "cacheRead")
USAGE_COST_CACHE_WRITE_KEYS: tuple[str, ...] = ("cache_write", "cacheWrite")


def _first_present(mapping: dict[str, object], keys: tuple[str, ...]) -> object | None:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _parse_usage_cost(raw_usage: dict[str, object]) -> float:
    raw_cost = _first_present(raw_usage, USAGE_COST_KEYS)
    if not isinstance(raw_cost, dict):
        return _coerce_float(raw_cost)

    cost_dict = cast(dict[str, object], raw_cost)
    total_cost = _first_present(cost_dict, USAGE_COST_TOTAL_KEYS)
    if total_cost is not None:
        return _coerce_float(total_cost)

    input_cost = _coerce_float(_first_present(cost_dict, USAGE_COST_INPUT_KEYS))
    output_cost = _coerce_float(_first_present(cost_dict, USAGE_COST_OUTPUT_KEYS))
    cache_read_cost = _coerce_float(_first_present(cost_dict, USAGE_COST_CACHE_READ_KEYS))
    cache_write_cost = _coerce_float(_first_present(cost_dict, USAGE_COST_CACHE_WRITE_KEYS))
    return input_cost + output_cost + cache_read_cost + cache_write_cost


def _parse_openrouter_usage(raw_usage: object) -> UsageMetrics | None:
    """Parse provider usage dict into canonical UsageMetrics.

    Supports all known tinyagent usage shapes:

    - OpenRouter raw SSE: ``prompt_tokens``, ``completion_tokens``,
      ``prompt_tokens_details.cached_tokens``
    - tinyagent normalized OpenRouter: ``prompt_tokens``, ``completion_tokens``, ``cacheRead``
    - alchemy (Rust) stream result: ``input``, ``output``, ``cache_read``, ``cost.total``

    If everything is zero/missing, returns None.
    """

    if not isinstance(raw_usage, dict):
        return None

    usage_dict = cast(dict[str, object], raw_usage)

    prompt_tokens = _coerce_int(_first_present(usage_dict, USAGE_PROMPT_TOKEN_KEYS))
    completion_tokens = _coerce_int(_first_present(usage_dict, USAGE_COMPLETION_TOKEN_KEYS))

    cached_tokens = _coerce_int(_first_present(usage_dict, USAGE_CACHE_READ_KEYS))
    if cached_tokens == 0:
        raw_details = _first_present(usage_dict, USAGE_PROMPT_DETAILS_KEYS)
        if isinstance(raw_details, dict):
            details = cast(dict[str, object], raw_details)
            cached_tokens = _coerce_int(_first_present(details, USAGE_PROMPT_DETAILS_CACHED_KEYS))

    cost = _parse_usage_cost(usage_dict)

    if prompt_tokens == 0 and completion_tokens == 0 and cached_tokens == 0 and cost == 0.0:
        return None

    return UsageMetrics(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cost=cost,
    )


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""

    max_iterations: int = DEFAULT_MAX_ITERATIONS
    debug_metrics: bool = False


@dataclass(slots=True)
class RequestContext:
    """Context for a single request."""

    request_id: str
    max_iterations: int
    debug_metrics: bool


@dataclass(slots=True)
class _TinyAgentStreamState:
    """Mutable per-run state for tinyagent event handling."""

    runtime: RuntimeState
    tool_start_times: dict[str, float]
    last_assistant_message: dict[str, Any] | None = None
    last_recorded_usage_id: int | None = None


class EmptyResponseHandler:
    """Handles tracking and intervention for empty responses."""

    def __init__(
        self,
        state_manager: StateManagerProtocol,
        notice_callback: NoticeCallback | None,
    ) -> None:
        self.state_manager = state_manager
        self.notice_callback = notice_callback

    def track(self, is_empty: bool) -> None:
        runtime = self.state_manager.session.runtime
        if is_empty:
            runtime.consecutive_empty_responses += 1
            return
        runtime.consecutive_empty_responses = 0

    def should_intervene(self) -> bool:
        runtime = self.state_manager.session.runtime
        return runtime.consecutive_empty_responses >= 1

    async def prompt_action(self, message: str, reason: str, iteration: int) -> None:
        logger = get_logger()
        logger.warning(f"Empty response: {reason}", iteration=iteration)

        show_thoughts = bool(getattr(self.state_manager.session, "show_thoughts", False))

        @dataclass
        class StateView:
            sm: StateManagerProtocol
            show_thoughts: bool

        state_view = StateView(sm=self.state_manager, show_thoughts=show_thoughts)
        notice = await ac.handle_empty_response(message, reason, iteration, state_view)
        if self.notice_callback:
            self.notice_callback(notice)
        self.state_manager.session.runtime.consecutive_empty_responses = 0


def _is_tinyagent_message(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    role = value.get("role")
    return role in {"user", "assistant", "tool_result"}


def _coerce_tinyagent_history(messages: list[Any]) -> list[dict[str, Any]]:
    if not messages:
        return []

    if all(_is_tinyagent_message(m) for m in messages):
        return [cast(dict[str, Any], m) for m in messages]

    raise TypeError(
        "Session history contains non-tinyagent messages. "
        "Back-compat for pydantic-ai sessions has been removed. "
        "Start a new session or delete the persisted session file."
    )


def _extract_assistant_text(message: dict[str, Any] | None) -> str:
    if not message:
        return ""

    if message.get("role") != "assistant":
        return ""

    content = message.get("content")
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)

    return "".join(parts)


def _extract_tool_result_text(result: Any) -> str | None:
    if result is None:
        return None

    content = getattr(result, "content", None)
    if not isinstance(content, list):
        return None

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)

    return "".join(parts) if parts else None


class RequestOrchestrator:
    """Orchestrates the request processing loop using tinyagent events."""

    def __init__(
        self,
        message: str,
        model: ModelName,
        state_manager: StateManagerProtocol,
        tool_callback: ToolCallback | None,
        streaming_callback: StreamingCallback | None,
        tool_result_callback: ToolResultCallback | None = None,
        tool_start_callback: ToolStartCallback | None = None,
        notice_callback: NoticeCallback | None = None,
        compaction_status_callback: CompactionStatusCallback | None = None,
    ) -> None:
        self.message = message
        self.model = model
        self.state_manager = state_manager
        self.tool_callback = tool_callback
        self.streaming_callback = streaming_callback
        self.tool_result_callback = tool_result_callback
        self.tool_start_callback = tool_start_callback
        self.notice_callback = notice_callback
        self.compaction_status_callback = compaction_status_callback
        self.compaction_controller = get_or_create_compaction_controller(state_manager)

        user_config = getattr(state_manager.session, "user_config", {}) or {}
        settings = user_config.get("settings", {})
        self.config = AgentConfig(
            max_iterations=int(settings.get("max_iterations", DEFAULT_MAX_ITERATIONS)),
            debug_metrics=bool(settings.get("debug_metrics", False)),
        )

        self.empty_handler = EmptyResponseHandler(state_manager, notice_callback)

    async def run(self) -> Agent:
        from tunacode.core.agents.agent_components.agent_config import (
            _coerce_global_request_timeout,
        )

        timeout = _coerce_global_request_timeout(self.state_manager.session)
        if timeout is None:
            return await self._run_impl()

        try:
            return await asyncio.wait_for(self._run_impl(), timeout=timeout)
        except TimeoutError as e:
            logger = get_logger()
            invalidated = ac.invalidate_agent_cache(self.model, self.state_manager)
            if invalidated:
                logger.lifecycle("Agent cache invalidated after timeout")
            raise GlobalRequestTimeoutError(timeout) from e

    async def _run_impl(self) -> Agent:
        ctx = self._initialize_request()
        logger = get_logger()
        logger.info("Request started", request_id=ctx.request_id)

        agent = ac.get_or_create_agent(self.model, self.state_manager)

        session = self.state_manager.session
        conversation = session.conversation
        history = _coerce_tinyagent_history(conversation.messages)

        self._configure_compaction_callbacks()
        compacted_history = await self._compact_history_for_request(history)

        baseline_message_count = len(conversation.messages)
        pre_request_history = list(conversation.messages)

        agent.replace_messages(compacted_history)
        session._debug_raw_stream_accum = ""

        try:
            await self._run_stream(
                agent=agent,
                request_context=ctx,
                baseline_message_count=baseline_message_count,
            )
            await self._retry_after_context_overflow_if_needed(
                agent=agent,
                request_context=ctx,
                pre_request_history=pre_request_history,
            )
            return agent
        except (UserAbortError, asyncio.CancelledError):
            self._handle_abort_cleanup(logger)
            raise

    def _initialize_request(self) -> RequestContext:
        ctx = self._create_request_context()
        self._reset_session_state()
        self._set_original_query_once()
        return ctx

    def _create_request_context(self) -> RequestContext:
        req_id = str(uuid.uuid4())[:REQUEST_ID_LENGTH]
        self.state_manager.session.runtime.request_id = req_id
        return RequestContext(
            request_id=req_id,
            max_iterations=self.config.max_iterations,
            debug_metrics=self.config.debug_metrics,
        )

    def _reset_session_state(self) -> None:
        session = self.state_manager.session
        runtime = session.runtime
        runtime.current_iteration = 0
        runtime.iteration_count = 0
        runtime.tool_registry.clear()
        runtime.batch_counter = 0
        runtime.consecutive_empty_responses = 0
        session.task.original_query = ""
        session.usage.last_call_usage = UsageMetrics()

    def _set_original_query_once(self) -> None:
        task_state = self.state_manager.session.task
        if task_state.original_query:
            return
        task_state.original_query = self.message

    def _configure_compaction_callbacks(self) -> None:
        self.compaction_controller.set_status_callback(self.compaction_status_callback)
        self.compaction_controller.set_usage_callback(self._record_compaction_usage)

    def _record_compaction_usage(self, raw_usage: dict[str, Any]) -> None:
        """Record usage from a compaction LLM call into session totals."""
        usage = _parse_openrouter_usage(raw_usage)
        if usage is None:
            logger = get_logger()
            logger.lifecycle(
                f"Compaction usage: raw payload not parseable, keys={sorted(raw_usage.keys())}"
            )
            return
        session = self.state_manager.session
        session.usage.session_total_usage.add(usage)
        logger = get_logger()
        logger.lifecycle(
            f"Compaction usage recorded: "
            f"prompt={usage.prompt_tokens} completion={usage.completion_tokens} "
            f"cost=${usage.cost:.4f}"
        )

    def _maybe_emit_compaction_notice(self, outcome: CompactionOutcome) -> None:
        if self.notice_callback is None:
            return

        notice = build_compaction_notice(outcome)
        if notice is None:
            return

        self.notice_callback(notice)

    async def _compact_history_for_request(
        self,
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        self.compaction_controller.reset_request_state()
        max_tokens = self.state_manager.session.conversation.max_tokens
        compaction_outcome = await self.compaction_controller.check_and_compact(
            history,
            max_tokens=max_tokens,
            signal=None,
            allow_threshold=True,
        )
        self._maybe_emit_compaction_notice(compaction_outcome)

        applied_messages = apply_compaction_messages(
            self.state_manager,
            compaction_outcome.messages,
        )
        return [cast(dict[str, Any], message) for message in applied_messages]

    async def _force_compact_history(
        self,
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        max_tokens = self.state_manager.session.conversation.max_tokens
        compaction_outcome = await self.compaction_controller.force_compact(
            history,
            max_tokens=max_tokens,
            signal=None,
        )
        self._maybe_emit_compaction_notice(compaction_outcome)

        applied_messages = apply_compaction_messages(
            self.state_manager,
            compaction_outcome.messages,
        )
        return [cast(dict[str, Any], message) for message in applied_messages]

    async def _retry_after_context_overflow_if_needed(
        self,
        *,
        agent: Agent,
        request_context: RequestContext,
        pre_request_history: list[dict[str, Any]],
    ) -> None:
        error_text = self._agent_error_text(agent)
        if not _is_context_overflow_error(error_text):
            return

        if self.notice_callback is not None:
            self.notice_callback(CONTEXT_OVERFLOW_RETRY_NOTICE)

        logger = get_logger()
        logger.warning("Context overflow detected; forcing compaction and retrying")

        conversation = self.state_manager.session.conversation
        apply_compaction_messages(self.state_manager, pre_request_history)

        forced_history = await self._force_compact_history(pre_request_history)

        agent.replace_messages(forced_history)
        self.state_manager.session._debug_raw_stream_accum = ""

        retry_baseline = len(conversation.messages)
        await self._run_stream(
            agent=agent,
            request_context=request_context,
            baseline_message_count=retry_baseline,
        )

        retry_error_text = self._agent_error_text(agent)
        if not _is_context_overflow_error(retry_error_text):
            return

        if self.notice_callback is not None:
            self.notice_callback(CONTEXT_OVERFLOW_FAILURE_NOTICE)

        estimated_tokens = estimate_messages_tokens(conversation.messages)
        max_tokens = conversation.max_tokens or DEFAULT_CONTEXT_WINDOW
        raise ContextOverflowError(
            estimated_tokens=estimated_tokens,
            max_tokens=max_tokens,
            model=self.model,
        )

    def _agent_error_text(self, agent: Agent) -> str:
        return _coerce_error_text(agent.state.get("error"))

    def _persist_agent_messages(self, agent: Any, baseline_message_count: int) -> None:
        session = self.state_manager.session
        conversation = session.conversation

        # Preserve anything that might have been appended externally during the run.
        external_messages = list(conversation.messages[baseline_message_count:])

        agent_messages = agent.state.get("messages", [])
        if not isinstance(agent_messages, list):
            raise TypeError("tinyagent Agent.state['messages'] must be a list")

        conversation.messages = [*agent_messages, *external_messages]

    async def _handle_stream_turn_end(
        self,
        event_obj: object,
        *,
        agent: Any,
        state: _TinyAgentStreamState,
        request_context: RequestContext,
        baseline_message_count: int,
    ) -> bool:
        _ = baseline_message_count

        turn_message = getattr(event_obj, "message", None)
        if isinstance(turn_message, dict):
            self._record_usage_from_assistant_message(
                cast(dict[str, Any], turn_message),
                source_event="turn_end",
                stream_state=state,
            )

        state.runtime.iteration_count += 1
        state.runtime.current_iteration = state.runtime.iteration_count

        if state.runtime.iteration_count <= request_context.max_iterations:
            return False

        agent.abort()
        raise RuntimeError(f"Max iterations exceeded ({request_context.max_iterations}); aborted")

    async def _handle_stream_message_update(
        self,
        event_obj: object,
        *,
        agent: Any,
        state: _TinyAgentStreamState,
        request_context: RequestContext,
        baseline_message_count: int,
    ) -> bool:
        _ = (agent, state, request_context, baseline_message_count)
        await self._handle_message_update(event_obj)
        return False

    def _record_usage_from_assistant_message(
        self,
        message: dict[str, Any],
        *,
        source_event: str,
        stream_state: _TinyAgentStreamState | None = None,
    ) -> None:
        if message.get("role") != "assistant":
            return

        raw_usage = message.get("usage")
        if not isinstance(raw_usage, dict):
            logger = get_logger()
            message_keys = sorted(message.keys())
            logger.warning(
                "Assistant message missing usage payload",
                source_event=source_event,
                usage_type=type(raw_usage).__name__,
                message_keys=message_keys,
            )
            return

        usage = _parse_openrouter_usage(raw_usage)
        if usage is None:
            logger = get_logger()
            usage_keys = sorted(raw_usage.keys())
            logger.warning(
                "Assistant usage payload did not match known schema",
                source_event=source_event,
                usage_keys=usage_keys,
                usage_payload=raw_usage,
            )
            return

        session = self.state_manager.session
        session.usage.last_call_usage = usage

        usage_id = id(raw_usage)
        already_recorded = (
            stream_state is not None and stream_state.last_recorded_usage_id == usage_id
        )
        if already_recorded:
            logger = get_logger()
            logger.lifecycle(f"Usage dedup: skipped duplicate from {source_event} (id={usage_id})")
            return

        if stream_state is not None:
            stream_state.last_recorded_usage_id = usage_id

        session.usage.session_total_usage.add(usage)

        logger = get_logger()
        logger.lifecycle(
            f"Usage recorded ({source_event}): "
            f"prompt={usage.prompt_tokens} completion={usage.completion_tokens} "
            f"cached={usage.cached_tokens} cost=${usage.cost:.4f} | "
            f"session_total: prompt={session.usage.session_total_usage.prompt_tokens} "
            f"completion={session.usage.session_total_usage.completion_tokens} "
            f"cost=${session.usage.session_total_usage.cost:.4f}"
        )

    async def _handle_stream_message_end(
        self,
        event_obj: object,
        *,
        agent: Any,
        state: _TinyAgentStreamState,
        request_context: RequestContext,
        baseline_message_count: int,
    ) -> bool:
        _ = (agent, request_context, baseline_message_count)

        msg = getattr(event_obj, "message", None)
        if not isinstance(msg, dict):
            return False

        if msg.get("role") != "assistant":
            return False

        state.last_assistant_message = cast(dict[str, Any], msg)
        self._record_usage_from_assistant_message(
            cast(dict[str, Any], msg),
            source_event="message_end",
            stream_state=state,
        )

        return False

    async def _handle_stream_tool_execution_start(
        self,
        event_obj: object,
        *,
        agent: Any,
        state: _TinyAgentStreamState,
        request_context: RequestContext,
        baseline_message_count: int,
    ) -> bool:
        _ = (agent, request_context, baseline_message_count)

        tool_call_id = cast(str, getattr(event_obj, "tool_call_id", ""))
        tool_name = cast(str, getattr(event_obj, "tool_name", ""))
        raw_args = getattr(event_obj, "args", None)

        state.tool_start_times[tool_call_id] = time.perf_counter()
        args = cast(dict[str, Any], raw_args or {})
        state.runtime.tool_registry.register(tool_call_id, tool_name, args)
        state.runtime.tool_registry.start(tool_call_id)

        if self.tool_start_callback is not None:
            self.tool_start_callback(tool_name)

        return False

    async def _handle_stream_tool_execution_end(
        self,
        event_obj: object,
        *,
        agent: Any,
        state: _TinyAgentStreamState,
        request_context: RequestContext,
        baseline_message_count: int,
    ) -> bool:
        _ = (agent, request_context, baseline_message_count)

        tool_call_id = cast(str, getattr(event_obj, "tool_call_id", ""))
        tool_name = cast(str, getattr(event_obj, "tool_name", ""))
        is_error = bool(getattr(event_obj, "is_error", False))
        result = getattr(event_obj, "result", None)

        duration_ms: float | None = None
        start_time = state.tool_start_times.pop(tool_call_id, None)
        if start_time is not None:
            duration_ms = (time.perf_counter() - start_time) * MILLISECONDS_PER_SECOND

        result_text = _extract_tool_result_text(result)

        if is_error:
            state.runtime.tool_registry.fail(tool_call_id, error=result_text)
        else:
            state.runtime.tool_registry.complete(tool_call_id, result=result_text)

        if self.tool_result_callback is None:
            return False

        args = state.runtime.tool_registry.get_args(tool_call_id) or {}
        status = "failed" if is_error else "completed"
        self.tool_result_callback(
            tool_name,
            status,
            cast(dict[str, Any], args),
            result_text,
            duration_ms,
        )

        return False

    async def _handle_stream_agent_end(
        self,
        event_obj: object,
        *,
        agent: Any,
        state: _TinyAgentStreamState,
        request_context: RequestContext,
        baseline_message_count: int,
    ) -> bool:
        _ = (event_obj, state, request_context)
        self._persist_agent_messages(agent, baseline_message_count)
        return True

    async def _run_stream(
        self,
        *,
        agent: Any,
        request_context: RequestContext,
        baseline_message_count: int,
    ) -> Agent:
        logger = get_logger()

        runtime = self.state_manager.session.runtime
        state = _TinyAgentStreamState(runtime=runtime, tool_start_times={})

        handlers: dict[str, Callable[..., Awaitable[bool]]] = {
            "turn_end": self._handle_stream_turn_end,
            "message_update": self._handle_stream_message_update,
            "message_end": self._handle_stream_message_end,
            "tool_execution_start": self._handle_stream_tool_execution_start,
            "tool_execution_end": self._handle_stream_tool_execution_end,
            "agent_end": self._handle_stream_agent_end,
        }

        started_at = time.perf_counter()

        async for event in agent.stream(self.message):
            ev_type = getattr(event, "type", None)
            if not isinstance(ev_type, str):
                continue

            handler = handlers.get(ev_type)
            if handler is None:
                continue

            should_stop = await handler(
                event,
                agent=agent,
                state=state,
                request_context=request_context,
                baseline_message_count=baseline_message_count,
            )
            if should_stop:
                break

        elapsed_ms = (time.perf_counter() - started_at) * MILLISECONDS_PER_SECOND
        logger.lifecycle(f"Request complete ({elapsed_ms:.0f}ms)")

        assistant_text = _extract_assistant_text(state.last_assistant_message)
        is_empty = not assistant_text.strip()
        self.empty_handler.track(is_empty)

        if is_empty and self.empty_handler.should_intervene():
            await self.empty_handler.prompt_action(
                self.message,
                "empty",
                runtime.iteration_count or 1,
            )

        return agent

    async def _handle_message_update(self, event: Any) -> None:
        if not self.streaming_callback:
            return

        assistant_event = getattr(event, "assistant_message_event", None)
        if not isinstance(assistant_event, dict):
            return

        if assistant_event.get("type") != "text_delta":
            return

        delta = assistant_event.get("delta")
        if not isinstance(delta, str) or not delta:
            return

        # Streaming callback is a UI hook; keep it best-effort.
        await self.streaming_callback(delta)

        # Keep legacy debug accumulator for abort handling.
        session = self.state_manager.session
        session._debug_raw_stream_accum += delta

    def _handle_abort_cleanup(self, logger: Any) -> None:
        session = self.state_manager.session
        conversation = session.conversation

        partial_text = session._debug_raw_stream_accum
        if partial_text.strip():
            interrupted_text = f"[INTERRUPTED]\n\n{partial_text}"
            conversation.messages.append(
                {
                    "role": "assistant",
                    "stop_reason": "aborted",
                    "content": [{"type": "text", "text": interrupted_text}],
                    "timestamp": int(time.time() * 1000),
                }
            )

        invalidated = ac.invalidate_agent_cache(self.model, self.state_manager)
        if invalidated:
            logger.lifecycle("Agent cache invalidated after abort")


def get_agent_tool() -> tuple[type[Any], type[Any]]:
    """Return the (Agent, AgentTool) classes."""

    from tinyagent import Agent as AgentCls
    from tinyagent.agent_types import AgentTool as ToolCls

    return AgentCls, ToolCls


async def process_request(
    message: str,
    model: ModelName,
    state_manager: StateManagerProtocol,
    tool_callback: ToolCallback | None = None,
    streaming_callback: StreamingCallback | None = None,
    tool_result_callback: ToolResultCallback | None = None,
    tool_start_callback: ToolStartCallback | None = None,
    notice_callback: NoticeCallback | None = None,
    compaction_status_callback: CompactionStatusCallback | None = None,
) -> Agent:
    orchestrator = RequestOrchestrator(
        message,
        model,
        state_manager,
        tool_callback,
        streaming_callback,
        tool_result_callback,
        tool_start_callback,
        notice_callback,
        compaction_status_callback,
    )
    return await orchestrator.run()
