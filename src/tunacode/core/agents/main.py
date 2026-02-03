"""Module: tunacode.core.agents.main

Refactored main agent functionality with focused responsibility classes.
Handles agent creation, configuration, and request processing.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool  # noqa: F401

from tunacode.constants import UI_COLORS
from tunacode.exceptions import GlobalRequestTimeoutError, UserAbortError
from tunacode.types import (
    ModelName,
    NoticeCallback,
    StreamingCallback,
    ToolCallback,
    ToolResultCallback,
    ToolStartCallback,
)

from tunacode.infrastructure.llm_types import AgentRun

from tunacode.core.agents.resume import log_message_history_debug, prune_old_tool_outputs
from tunacode.core.agents.resume.sanitize import (
    remove_consecutive_requests,
    remove_dangling_tool_calls,
    remove_empty_responses,
    run_cleanup_loop,
    sanitize_history_for_resume,
)
from tunacode.core.logging import get_logger
from tunacode.core.types import StateManagerProtocol

from . import agent_components as ac


class DotDict(dict):
    """dot.notation access to dictionary attributes."""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore[assignment]
    __delattr__ = dict.__delitem__  # type: ignore[assignment]


colors = DotDict(UI_COLORS)

__all__ = [
    "process_request",
    "get_agent_tool",
    "check_query_satisfaction",
]

DEFAULT_MAX_ITERATIONS: int = 15
REQUEST_ID_LENGTH: int = 8
MESSAGE_PREVIEW_LENGTH: int = 50
DEBUG_HISTORY_SAMPLE_SIZE: int = 3
DEBUG_HISTORY_PARTS_LIMIT: int = 5
MILLISECONDS_PER_SECOND: int = 1000


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
        """Track empty response and increment counter if empty."""
        session = self.state_manager.session
        runtime = session.runtime
        if is_empty:
            current = runtime.consecutive_empty_responses
            runtime.consecutive_empty_responses = current + 1
        else:
            runtime.consecutive_empty_responses = 0

    def should_intervene(self) -> bool:
        """Check if intervention is needed (>= 1 consecutive empty)."""
        runtime = self.state_manager.session.runtime
        return runtime.consecutive_empty_responses >= 1

    async def prompt_action(self, message: str, reason: str, iteration: int) -> None:
        """Delegate to agent_components.handle_empty_response."""
        logger = get_logger()
        logger.warning(f"Empty response: {reason}", iteration=iteration)

        # Create a minimal state-like object for compatibility
        class StateProxy:
            def __init__(self, sm: StateManagerProtocol) -> None:
                self.sm = sm
                self.show_thoughts = bool(getattr(sm.session, "show_thoughts", False))

        state_proxy = StateProxy(self.state_manager)
        notice = await ac.handle_empty_response(message, reason, iteration, state_proxy)
        if self.notice_callback:
            self.notice_callback(notice)
        # Clear after intervention
        self.state_manager.session.runtime.consecutive_empty_responses = 0


class IterationManager:
    """Manages iteration tracking."""

    def __init__(self, state_manager: StateManagerProtocol) -> None:
        self.state_manager = state_manager

    def update_counters(self, iteration: int) -> None:
        """Update session iteration counters."""
        runtime = self.state_manager.session.runtime
        runtime.current_iteration = iteration
        runtime.iteration_count = iteration


class RequestOrchestrator:
    """Orchestrates the main request processing loop."""

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
    ) -> None:
        self.message = message
        self.model = model
        self.state_manager = state_manager
        self.tool_callback = tool_callback
        self.streaming_callback = streaming_callback
        self.tool_result_callback = tool_result_callback
        self.tool_start_callback = tool_start_callback

        # Initialize config from session settings
        user_config = getattr(state_manager.session, "user_config", {}) or {}
        settings = user_config.get("settings", {})
        self.config = AgentConfig(
            max_iterations=int(settings.get("max_iterations", DEFAULT_MAX_ITERATIONS)),
            debug_metrics=bool(settings.get("debug_metrics", False)),
        )

        # Initialize managers
        self.empty_handler = EmptyResponseHandler(state_manager, notice_callback)
        self.iteration_manager = IterationManager(state_manager)

    def _init_request_context(self) -> RequestContext:
        """Initialize request context with ID and config."""
        req_id = str(uuid.uuid4())[:REQUEST_ID_LENGTH]
        self.state_manager.session.runtime.request_id = req_id

        return RequestContext(
            request_id=req_id,
            max_iterations=self.config.max_iterations,
            debug_metrics=self.config.debug_metrics,
        )

    def _reset_session_state(self) -> None:
        """Reset/initialize fields needed for a new run."""
        session = self.state_manager.session
        runtime = session.runtime
        task_state = session.task

        runtime.current_iteration = 0
        runtime.iteration_count = 0
        runtime.tool_registry.clear()

        runtime.batch_counter = 0

        # Track empty response streaks
        runtime.consecutive_empty_responses = 0

        task_state.original_query = ""

    def _set_original_query_once(self, query: str) -> None:
        """Set original query if not already set."""
        task_state = self.state_manager.session.task
        if not task_state.original_query:
            task_state.original_query = query

    def _persist_run_messages(self, agent_run: AgentRun, baseline_message_count: int) -> None:
        """Persist authoritative run messages, preserving external additions."""
        run_messages = list(agent_run.all_messages())
        conversation = self.state_manager.session.conversation
        external_messages = conversation.messages[baseline_message_count:]
        merged_messages = [*run_messages, *external_messages]

        conversation.messages = merged_messages

    async def run(self) -> AgentRun:
        """Run the main request processing loop with optional global timeout."""
        from tunacode.core.agents.agent_components.agent_config import (
            _coerce_global_request_timeout,
        )

        timeout = _coerce_global_request_timeout(self.state_manager.session)
        if timeout is None:
            return await self._run_impl()

        try:
            return await asyncio.wait_for(self._run_impl(), timeout=timeout)
        except TimeoutError as e:
            # Invalidate agent cache - HTTP client may be in bad state after timeout
            logger = get_logger()
            invalidated = ac.invalidate_agent_cache(self.model, self.state_manager)
            if invalidated:
                logger.lifecycle("Agent cache invalidated after timeout")
            raise GlobalRequestTimeoutError(timeout) from e

    async def _run_impl(self) -> AgentRun:
        """Internal implementation of request processing loop."""
        ctx = self._initialize_request()

        logger = get_logger()
        request_id = ctx.request_id
        logger.info("Request started", request_id=request_id)

        agent = ac.get_or_create_agent(self.model, self.state_manager)

        message_history, debug_mode, baseline_message_count = self._prepare_message_history(logger)

        response_state = ac.ResponseState()

        try:
            return await self._run_agent_iterations(
                agent=agent,
                message_history=message_history,
                debug_mode=debug_mode,
                response_state=response_state,
                baseline_message_count=baseline_message_count,
                request_context=ctx,
                logger=logger,
            )
        except (UserAbortError, asyncio.CancelledError):
            self._handle_abort_cleanup(logger)
            raise

    def _initialize_request(self) -> RequestContext:
        """Initialize request context and reset per-run session state."""
        ctx = self._init_request_context()
        self._reset_session_state()
        self._set_original_query_once(self.message)
        return ctx

    def _prepare_message_history(self, logger: Any) -> tuple[list[Any], bool, int]:
        """Prepare and sanitize message history for the next agent run."""
        session = self.state_manager.session
        conversation = session.conversation
        runtime = session.runtime

        session_messages = conversation.messages
        tool_registry = runtime.tool_registry

        self._log_pruned_tool_outputs(session_messages, logger)

        debug_mode = bool(getattr(session, "debug_mode", False))

        _, dangling_tool_call_ids = run_cleanup_loop(session_messages, tool_registry)

        self._drop_trailing_request_if_needed(session_messages, logger)

        if debug_mode:
            log_message_history_debug(
                session_messages,
                self.message,
                dangling_tool_call_ids,
            )

        baseline_message_count = len(session_messages)
        self._log_history_state(session_messages, baseline_message_count, logger)

        message_history = sanitize_history_for_resume(session_messages)
        self._log_sanitized_history_state(message_history, debug_mode, logger)

        return message_history, debug_mode, baseline_message_count

    def _log_pruned_tool_outputs(self, session_messages: list[Any], logger: Any) -> None:
        """Prune old tool outputs and log reclaimed tokens."""
        _, tokens_reclaimed = prune_old_tool_outputs(session_messages, self.model)
        has_reclaimed_tokens = tokens_reclaimed > 0
        if not has_reclaimed_tokens:
            return
        logger.lifecycle(f"History pruned ({tokens_reclaimed} tokens reclaimed)")

    def _drop_trailing_request_if_needed(
        self,
        session_messages: list[Any],
        logger: Any,
    ) -> bool:
        """Remove a trailing request if we are about to enqueue a new one."""
        has_messages = bool(session_messages)
        has_new_message = bool(self.message)
        should_check = has_messages and has_new_message
        if not should_check:
            return False

        last_msg = session_messages[-1]
        last_kind = getattr(last_msg, "kind", None)
        if isinstance(last_msg, dict):
            last_kind = last_msg.get("kind")

        if last_kind != "request":
            return False

        logger.lifecycle("Dropping trailing request to avoid consecutive requests")
        session_messages.pop()
        return True

    def _log_history_state(
        self,
        session_messages: list[Any],
        baseline_message_count: int,
        logger: Any,
    ) -> None:
        """Log the current history state for corruption diagnostics."""
        if not session_messages:
            return

        last_msg = session_messages[-1]
        last_kind = getattr(last_msg, "kind", "unknown")
        last_parts = getattr(last_msg, "parts", [])
        last_parts_count = len(last_parts)
        has_tool_calls = _message_has_tool_calls(last_msg)
        logger.debug(
            f"History state: {baseline_message_count} messages, "
            f"last_kind={last_kind}, parts={last_parts_count}, "
            f"has_tool_calls={has_tool_calls}"
        )

        message_sample = session_messages[-DEBUG_HISTORY_SAMPLE_SIZE:]
        for idx, msg in enumerate(message_sample):
            msg_kind = getattr(msg, "kind", "?")
            msg_parts = getattr(msg, "parts", [])
            parts_summary = []
            parts_to_log = msg_parts[:DEBUG_HISTORY_PARTS_LIMIT]
            for part in parts_to_log:
                part_kind = getattr(part, "part_kind", "?")
                part_content = getattr(part, "content", None)
                content_preview = ""
                if isinstance(part_content, str):
                    content_preview = f":{len(part_content)}chars"
                parts_summary.append(f"{part_kind}{content_preview}")
            reverse_index = DEBUG_HISTORY_SAMPLE_SIZE - idx
            logger.debug(
                f"  msg[-{reverse_index}]: kind={msg_kind}, parts=[{', '.join(parts_summary)}]"
            )

    def _log_sanitized_history_state(
        self,
        message_history: list[Any],
        debug_mode: bool,
        logger: Any,
    ) -> None:
        """Log sanitized message history details for debug mode."""
        if not debug_mode:
            return

        type_names = (
            [type(m).__name__ for m in message_history[:DEBUG_HISTORY_SAMPLE_SIZE]]
            if message_history
            else []
        )
        logger.debug(f"message_history count={len(message_history)}, types={type_names}")
        if not message_history:
            return

        logger.debug(
            f"message_history[0]: {type(message_history[0]).__name__} "
            f"kind={getattr(message_history[0], 'kind', 'unknown')}"
        )
        has_multiple_messages = len(message_history) > 1
        if not has_multiple_messages:
            return

        logger.debug(
            f"message_history[-1]: {type(message_history[-1]).__name__} "
            f"kind={getattr(message_history[-1], 'kind', 'unknown')}"
        )

    async def _run_agent_iterations(
        self,
        agent: Agent,
        message_history: list[Any],
        debug_mode: bool,
        response_state: ac.ResponseState,
        baseline_message_count: int,
        request_context: RequestContext,
        logger: Any,
    ) -> ac.AgentRunWithState:
        msg_preview = self.message[:MESSAGE_PREVIEW_LENGTH]
        history_len = len(message_history)
        logger.debug(f"Starting agent.iter(): msg={msg_preview}... history={history_len}")
        async with agent.iter(self.message, message_history=message_history) as run_handle:
            logger.debug("agent.iter() context entered successfully")
            if debug_mode:
                self._log_run_handle_context_messages(run_handle, logger)

            agent_run_ctx = run_handle.ctx
            iteration_index = 1
            async for node in run_handle:
                should_stop = await self._handle_iteration_node(
                    node=node,
                    iteration_index=iteration_index,
                    agent_run_ctx=agent_run_ctx,
                    request_id=request_context.request_id,
                    response_state=response_state,
                    logger=logger,
                )
                if should_stop:
                    break
                iteration_index += 1

            self._persist_run_messages(run_handle, baseline_message_count)
            logger.lifecycle("Request complete")
            return ac.AgentRunWithState(run_handle, response_state)

    def _log_run_handle_context_messages(self, run_handle: AgentRun, logger: Any) -> None:
        """Log pydantic-ai context messages for debug."""
        if not hasattr(run_handle, "ctx"):
            return

        ctx_messages = getattr(run_handle.ctx, "messages", None)
        if ctx_messages is None:
            run_state = getattr(run_handle.ctx, "state", None)
            if run_state is not None:
                ctx_messages = getattr(run_state, "message_history", None)

        if ctx_messages is not None:
            logger.debug(f"pydantic-ai ctx.messages count={len(ctx_messages)}")
            if ctx_messages:
                logger.debug(f"ctx.messages[0] type={type(ctx_messages[0]).__name__}")
            return

        logger.debug("pydantic-ai ctx.messages not found or None")

    async def _handle_iteration_node(
        self,
        node: Any,
        iteration_index: int,
        agent_run_ctx: Any,
        request_id: str,
        response_state: ac.ResponseState,
        logger: Any,
    ) -> bool:
        iter_start = time.perf_counter()
        logger.lifecycle(f"--- Iteration {iteration_index} ---")

        self._log_node_details(node, logger)

        self.iteration_manager.update_counters(iteration_index)

        streaming_callback = self.streaming_callback
        can_stream = streaming_callback is not None
        is_request_node = Agent.is_model_request_node(node)
        should_stream = can_stream and is_request_node
        if should_stream and streaming_callback is not None:
            await ac.stream_model_request_node(
                node,
                agent_run_ctx,
                self.state_manager,
                streaming_callback,
                request_id,
                iteration_index,
            )

        empty_response, empty_reason = await ac.process_node(
            node,
            self.tool_callback,
            self.state_manager,
            streaming_callback,
            response_state,
            self.tool_result_callback,
            self.tool_start_callback,
        )
        iter_elapsed_ms = (time.perf_counter() - iter_start) * MILLISECONDS_PER_SECOND
        logger.lifecycle(f"Iteration {iteration_index} complete ({iter_elapsed_ms:.0f}ms)")

        self.empty_handler.track(empty_response)
        should_prompt = empty_response and self.empty_handler.should_intervene()
        if should_prompt:
            prompt_reason = empty_reason or ""
            await self.empty_handler.prompt_action(self.message, prompt_reason, iteration_index)

        self._update_response_state_from_node(node, response_state)

        if response_state.task_completed:
            logger.lifecycle(f"Task completed at iteration {iteration_index}")
            return True

        return False

    def _log_node_details(self, node: Any, logger: Any) -> None:
        """Log node details for debug visibility."""
        node_type = type(node).__name__
        has_request = getattr(node, "request", None) is not None
        has_response = getattr(node, "model_response", None) is not None
        has_thought = getattr(node, "thought", None) is not None
        logger.debug(
            f"Node: type={node_type}, "
            f"has_request={has_request}, has_response={has_response}, "
            f"has_thought={has_thought}"
        )

    def _update_response_state_from_node(
        self,
        node: Any,
        response_state: ac.ResponseState,
    ) -> None:
        """Update response state based on node output."""
        node_output = getattr(getattr(node, "result", None), "output", None)
        if not node_output:
            return
        response_state.has_user_response = True

    def _handle_abort_cleanup(self, logger: Any) -> None:
        """Clean up session state after abort or cancellation."""
        session = self.state_manager.session
        conversation = session.conversation
        runtime = session.runtime

        partial_text = session._debug_raw_stream_accum
        has_partial_text = bool(partial_text.strip())
        if has_partial_text:
            from pydantic_ai.messages import ModelResponse, TextPart

            interrupted_text = f"[INTERRUPTED]\n\n{partial_text}"
            partial_msg = ModelResponse(parts=[TextPart(content=interrupted_text)])
            conversation.messages.append(partial_msg)

        remove_dangling_tool_calls(conversation.messages, runtime.tool_registry)
        remove_empty_responses(conversation.messages)
        remove_consecutive_requests(conversation.messages)

        invalidated = ac.invalidate_agent_cache(self.model, self.state_manager)
        if invalidated:
            logger.lifecycle("Agent cache invalidated after abort")


# Utility functions


def _message_has_tool_calls(message: Any) -> bool:
    """Return True if message contains tool calls in parts or metadata.

    Handles both pydantic-ai message objects and raw dicts (from failed deserialization).
    """
    # Handle both object and dict forms (dicts occur when deserialization fails)
    if isinstance(message, dict):
        parts = message.get("parts", [])
        tool_calls = message.get("tool_calls", [])
    else:
        parts = getattr(message, "parts", [])
        tool_calls = getattr(message, "tool_calls", [])

    if tool_calls:
        return True

    for part in parts:
        if isinstance(part, dict):
            part_kind = part.get("part_kind")
        else:
            part_kind = getattr(part, "part_kind", None)
        if part_kind == "tool-call":
            return True

    return False


def get_agent_tool() -> tuple[type[Agent], type[Tool]]:
    """Return Agent and Tool classes without importing at module load time."""
    from pydantic_ai import Agent as AgentCls
    from pydantic_ai import Tool as ToolCls

    return AgentCls, ToolCls


async def check_query_satisfaction(
    agent: Agent,
    original_query: str,
    response: str,
    state_manager: StateManagerProtocol,
) -> bool:
    """Legacy hook for compatibility; completion still signaled via DONE marker."""
    return True


async def process_request(
    message: str,
    model: ModelName,
    state_manager: StateManagerProtocol,
    tool_callback: ToolCallback | None = None,
    streaming_callback: StreamingCallback | None = None,
    tool_result_callback: ToolResultCallback | None = None,
    tool_start_callback: ToolStartCallback | None = None,
    notice_callback: NoticeCallback | None = None,
) -> AgentRun:
    orchestrator = RequestOrchestrator(
        message,
        model,
        state_manager,
        tool_callback,
        streaming_callback,
        tool_result_callback,
        tool_start_callback,
        notice_callback,
    )
    return await orchestrator.run()
