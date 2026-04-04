"""Main agent functionality for the tinyagent event-stream orchestrator."""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from typing import cast

from tinyagent.agent import Agent, extract_text
from tinyagent.agent_types import (
    AgentEndEvent,
    AgentEvent,
    AgentMessage,
    AgentTool,
    AssistantMessage,
    MessageEndEvent,
    MessageUpdateEvent,
    TextContent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    TurnEndEvent,
    is_agent_end_event,
    is_message_end_event,
    is_tool_execution_end_event,
    is_tool_execution_start_event,
    is_turn_end_event,
)

from tunacode.constants import DEFAULT_CONTEXT_WINDOW
from tunacode.exceptions import (
    AgentError,
    ContextOverflowError,
    GlobalRequestTimeoutError,
    UserAbortError,
)
from tunacode.types import (
    ModelName,
    NoticeCallback,
    StreamingCallback,
    ToolResultCallback,
    ToolStartCallback,
    UsageMetrics,
)
from tunacode.utils.messaging import estimate_message_tokens, estimate_messages_tokens

from tunacode.core.compaction.controller import (
    CompactionStatusCallback,
    apply_compaction_messages,
    build_compaction_notice,
    get_or_create_compaction_controller,
)
from tunacode.core.compaction.types import CompactionOutcome
from tunacode.core.debug.usage_trace import log_usage_update
from tunacode.core.logging.manager import LogManager, get_logger
from tunacode.core.types.state import StateManagerProtocol

from . import agent_components as ac
from .agent_components.agent_config import _coerce_global_request_timeout, _coerce_max_iterations
from .helpers import (
    CONTEXT_OVERFLOW_FAILURE_NOTICE,
    CONTEXT_OVERFLOW_RETRY_NOTICE,
    _TinyAgentStreamState,
    canonicalize_tool_result,
    coerce_error_text,
    extract_tool_result_text,
    is_context_overflow_error,
    parse_canonical_usage,
)

REQUEST_ID_LENGTH = 8
MILLISECONDS_PER_SECOND = 1000
STREAM_EVENT_GAP_WARN_MS = 250.0


def _describe_stream_event(event: AgentEvent) -> str:
    if isinstance(event, MessageUpdateEvent):
        assistant_event = event.assistant_message_event
        if assistant_event is None:
            return "message_update/none"
        return f"message_update/{assistant_event.type}"
    if is_message_end_event(event):
        return "message_end"
    if is_tool_execution_start_event(event):
        return f"tool_start/{event.tool_name}"
    if isinstance(event, ToolExecutionUpdateEvent):
        return f"tool_update/{event.tool_name}"
    if is_tool_execution_end_event(event):
        return f"tool_end/{event.tool_name}"
    if is_turn_end_event(event):
        return "turn_end"
    if is_agent_end_event(event):
        return "agent_end"
    return type(event).__name__


class RequestOrchestrator:
    """Orchestrates the request processing loop using tinyagent events."""

    def __init__(
        self,
        message: str,
        model: ModelName,
        state_manager: StateManagerProtocol,
        streaming_callback: StreamingCallback | None,
        thinking_callback: StreamingCallback | None = None,
        tool_result_callback: ToolResultCallback | None = None,
        tool_start_callback: ToolStartCallback | None = None,
        notice_callback: NoticeCallback | None = None,
        compaction_status_callback: CompactionStatusCallback | None = None,
    ) -> None:
        self.message = message
        self.model = model
        self.state_manager = state_manager
        self.streaming_callback = streaming_callback
        self.thinking_callback = thinking_callback
        self.tool_result_callback = tool_result_callback
        self.tool_start_callback = tool_start_callback
        self.notice_callback = notice_callback
        self.compaction_status_callback = compaction_status_callback
        self.compaction_controller = get_or_create_compaction_controller(state_manager)
        self._active_stream_state: _TinyAgentStreamState | None = None

    async def run(self) -> Agent:
        timeout = _coerce_global_request_timeout(self.state_manager.session)
        if timeout is None:
            return await self._run_impl()
        try:
            return await asyncio.wait_for(self._run_impl(), timeout=timeout)
        except TimeoutError as exc:
            self._invalidate_agent_cache_after_timeout(timeout)
            raise GlobalRequestTimeoutError(timeout) from exc

    def _invalidate_agent_cache_after_timeout(self, timeout: float) -> None:
        _ = timeout
        logger = get_logger()
        if ac.invalidate_agent_cache(self.model, self.state_manager):
            logger.lifecycle("Agent cache invalidated after timeout")

    async def _run_impl(self) -> Agent:
        max_iterations = self._initialize_request()
        logger = get_logger()
        logger.info("Request started", request_id=self.state_manager.session.runtime.request_id)

        session = self.state_manager.session
        conversation = session.conversation
        pre_stream_started_at = time.perf_counter()

        agent_started_at = time.perf_counter()
        agent = ac.get_or_create_agent(self.model, self.state_manager)
        agent_duration_ms = (time.perf_counter() - agent_started_at) * MILLISECONDS_PER_SECOND
        logger.lifecycle(f"Init: get_or_create_agent dur={agent_duration_ms:.1f}ms")

        self.compaction_controller.set_status_callback(self.compaction_status_callback)

        compaction_started_at = time.perf_counter()
        compacted_history = await self._compact_history_for_request(conversation.messages)
        compaction_duration_ms = (
            time.perf_counter() - compaction_started_at
        ) * MILLISECONDS_PER_SECOND
        logger.lifecycle(
            "Init: "
            f"compaction in={len(conversation.messages)} "
            f"out={len(compacted_history)} "
            f"dur={compaction_duration_ms:.1f}ms"
        )

        baseline_message_count = len(conversation.messages)
        pre_request_history = list(conversation.messages)

        replace_messages_started_at = time.perf_counter()
        agent.replace_messages(compacted_history)
        replace_messages_duration_ms = (
            time.perf_counter() - replace_messages_started_at
        ) * MILLISECONDS_PER_SECOND
        logger.lifecycle(
            "Init: "
            f"replace_messages count={len(compacted_history)} "
            f"dur={replace_messages_duration_ms:.1f}ms"
        )
        pre_stream_duration_ms = (
            time.perf_counter() - pre_stream_started_at
        ) * MILLISECONDS_PER_SECOND
        logger.lifecycle(f"Init: pre_stream total={pre_stream_duration_ms:.1f}ms")
        session._debug_raw_stream_accum = ""

        try:
            await self._run_stream(
                agent=agent,
                max_iterations=max_iterations,
                baseline_message_count=baseline_message_count,
            )
            await self._retry_after_context_overflow_if_needed(
                agent=agent,
                max_iterations=max_iterations,
                pre_request_history=pre_request_history,
            )
            return agent
        except (UserAbortError, asyncio.CancelledError):
            self._handle_abort_cleanup(
                logger,
                agent=agent,
                baseline_message_count=baseline_message_count,
                invalidate_cache=False,
            )
            raise

    def _initialize_request(self) -> int:
        request_id = str(uuid.uuid4())[:REQUEST_ID_LENGTH]
        session = self.state_manager.session
        runtime = session.runtime
        runtime.request_id = request_id
        runtime.current_iteration = 0
        runtime.iteration_count = 0
        runtime.tool_registry.clear()
        runtime.batch_counter = 0
        session.usage.last_call_usage = UsageMetrics()
        if not session.task.original_query:
            session.task.original_query = self.message
        return _coerce_max_iterations(session)

    def _maybe_emit_compaction_notice(self, outcome: CompactionOutcome) -> None:
        if self.notice_callback is None:
            return
        notice = build_compaction_notice(outcome)
        if notice is not None:
            self.notice_callback(notice)

    async def _compact_history_for_request(self, history: list[AgentMessage]) -> list[AgentMessage]:
        self.compaction_controller.reset_request_state()
        outcome = await self.compaction_controller.check_and_compact(
            history,
            max_tokens=self.state_manager.session.conversation.max_tokens,
            signal=None,
            allow_threshold=True,
        )
        self._maybe_emit_compaction_notice(outcome)
        return apply_compaction_messages(self.state_manager, outcome.messages)

    async def _force_compact_history(self, history: list[AgentMessage]) -> list[AgentMessage]:
        outcome = await self.compaction_controller.force_compact(
            history,
            max_tokens=self.state_manager.session.conversation.max_tokens,
            signal=None,
        )
        self._maybe_emit_compaction_notice(outcome)
        return apply_compaction_messages(self.state_manager, outcome.messages)

    async def _retry_after_context_overflow_if_needed(
        self,
        *,
        agent: Agent,
        max_iterations: int,
        pre_request_history: list[AgentMessage],
    ) -> None:
        error_text = self._agent_error_text(agent)
        if not is_context_overflow_error(error_text):
            return

        logger = get_logger()
        logger.warning("Context overflow detected; forcing compaction and retrying")
        if self.notice_callback is not None:
            self.notice_callback(CONTEXT_OVERFLOW_RETRY_NOTICE)

        conversation = self.state_manager.session.conversation
        apply_compaction_messages(self.state_manager, pre_request_history)
        forced_history = await self._force_compact_history(pre_request_history)
        agent.replace_messages(forced_history)
        self.state_manager.session._debug_raw_stream_accum = ""
        await self._run_stream(
            agent=agent,
            max_iterations=max_iterations,
            baseline_message_count=len(conversation.messages),
        )

        retry_error_text = self._agent_error_text(agent)
        if not is_context_overflow_error(retry_error_text):
            return

        if self.notice_callback is not None:
            self.notice_callback(CONTEXT_OVERFLOW_FAILURE_NOTICE)
        estimated_tokens = conversation.total_tokens
        if estimated_tokens == 0 and conversation.messages:
            estimated_tokens = estimate_messages_tokens(conversation.messages)
            conversation.total_tokens = estimated_tokens

        raise ContextOverflowError(
            estimated_tokens=estimated_tokens,
            max_tokens=conversation.max_tokens or DEFAULT_CONTEXT_WINDOW,
            model=self.model,
        )

    def _agent_error_text(self, agent: Agent) -> str:
        return coerce_error_text(agent.state.error)

    def _mark_tool_start_batch_state(
        self, state: _TinyAgentStreamState, *, tool_call_id: str
    ) -> None:
        if state.active_tool_call_ids:
            state.batch_tool_call_ids.update(state.active_tool_call_ids)
            state.batch_tool_call_ids.add(tool_call_id)
        state.active_tool_call_ids.add(tool_call_id)

    def _clear_tool_batch_state_if_idle(self, state: _TinyAgentStreamState) -> None:
        if not state.active_tool_call_ids:
            state.batch_tool_call_ids.clear()

    def _resolve_tool_duration_ms(
        self,
        state: _TinyAgentStreamState,
        *,
        tool_call_id: str,
    ) -> float | None:
        start_time = state.tool_start_times.pop(tool_call_id, None)
        if start_time is None or tool_call_id in state.batch_tool_call_ids:
            return None
        return (time.perf_counter() - start_time) * MILLISECONDS_PER_SECOND

    def _persist_agent_messages(self, agent: Agent, baseline_message_count: int) -> None:
        conversation = self.state_manager.session.conversation
        external_messages = list(conversation.messages[baseline_message_count:])
        conversation.messages = [*list(agent.state.messages), *external_messages]
        conversation.total_tokens = estimate_messages_tokens(conversation.messages)

    def _remove_in_flight_tool_registry_entries(self, logger: LogManager) -> None:
        active_stream_state = self._active_stream_state
        if active_stream_state is None:
            return

        unresolved_tool_call_ids = set(active_stream_state.active_tool_call_ids)
        if not unresolved_tool_call_ids:
            return

        removed_count = self.state_manager.session.runtime.tool_registry.remove_many(
            unresolved_tool_call_ids
        )
        if removed_count > 0:
            logger.lifecycle(f"Removed {removed_count} in-flight tool call(s) after abort")

    def _rollback_to_last_stable_turn(
        self,
        logger: LogManager,
        *,
        agent: Agent,
        baseline_message_count: int,
    ) -> None:
        active_state = self._active_stream_state
        if active_state is None:
            self._persist_agent_messages(agent, baseline_message_count)
            return

        stable_count = active_state.last_stable_agent_message_count
        all_agent_messages = list(agent.state.messages)
        rolled_back_messages = all_agent_messages[:stable_count]
        dropped_count = len(all_agent_messages) - stable_count

        conversation = self.state_manager.session.conversation
        external_messages = list(conversation.messages[baseline_message_count:])
        conversation.messages = [*rolled_back_messages, *external_messages]
        conversation.total_tokens = estimate_messages_tokens(conversation.messages)

        if dropped_count > 0:
            logger.lifecycle(
                f"Rolled back {dropped_count} in-flight message(s) to last stable turn"
            )

    def _append_interrupted_partial_message(self) -> None:
        session = self.state_manager.session
        partial_text = session._debug_raw_stream_accum
        if not partial_text.strip():
            return

        latest_assistant_text = ""
        for message in reversed(session.conversation.messages):
            if isinstance(message, AssistantMessage):
                latest_assistant_text = extract_text(message)
                break
        if latest_assistant_text.strip() == partial_text.strip():
            return

        interrupted_message = AssistantMessage(
            content=[TextContent(text=f"[INTERRUPTED]\n\n{partial_text}")],
            stop_reason="aborted",
            timestamp=int(time.time() * MILLISECONDS_PER_SECOND),
        )
        session.conversation.messages.append(interrupted_message)
        session.conversation.total_tokens += estimate_message_tokens(interrupted_message)

    async def _handle_stream_turn_end(
        self,
        event_obj: TurnEndEvent,
        *,
        agent: Agent,
        state: _TinyAgentStreamState,
        max_iterations: int,
        baseline_message_count: int,
    ) -> bool:
        _ = (event_obj, baseline_message_count)
        state.last_stable_agent_message_count = len(agent.state.messages)
        state.runtime.iteration_count += 1
        state.runtime.current_iteration = state.runtime.iteration_count
        if state.runtime.iteration_count <= max_iterations:
            return False
        agent.abort()
        raise RuntimeError(f"Max iterations exceeded ({max_iterations}); aborted")

    async def _handle_stream_message_update(
        self,
        event_obj: MessageUpdateEvent,
        *,
        agent: Agent,
        state: _TinyAgentStreamState,
        baseline_message_count: int,
    ) -> bool:
        _ = (agent, state, baseline_message_count)
        await self._handle_message_update(event_obj)
        return False

    async def _handle_stream_message_end(
        self,
        event_obj: MessageEndEvent,
        *,
        agent: Agent,
        state: _TinyAgentStreamState,
        baseline_message_count: int,
    ) -> bool:
        _ = (agent, baseline_message_count)
        if not isinstance(event_obj.message, AssistantMessage):
            return False
        state.last_assistant_message = event_obj.message
        usage = parse_canonical_usage(event_obj.message.usage)
        session = self.state_manager.session
        session.usage.last_call_usage = usage
        session.usage.session_total_usage.add(usage)
        log_usage_update(
            logger=get_logger(),
            request_id=session.runtime.request_id,
            event_name="message_end",
            last_call_usage=session.usage.last_call_usage,
            session_total_usage=session.usage.session_total_usage,
        )
        return False

    async def _handle_stream_tool_execution_start(
        self,
        event_obj: ToolExecutionStartEvent,
        *,
        agent: Agent,
        state: _TinyAgentStreamState,
        baseline_message_count: int,
    ) -> bool:
        _ = (agent, baseline_message_count)
        tool_call_id = event_obj.tool_call_id
        tool_name = event_obj.tool_name
        args = event_obj.args or {}
        state.tool_start_times[tool_call_id] = time.perf_counter()
        self._mark_tool_start_batch_state(state, tool_call_id=tool_call_id)
        state.runtime.tool_registry.register(
            tool_call_id,
            tool_name,
            args,
        )
        state.runtime.tool_registry.start(tool_call_id)
        if self.tool_start_callback is not None:
            self.tool_start_callback(tool_name)
        return False

    async def _handle_stream_tool_execution_end(
        self,
        event_obj: ToolExecutionEndEvent,
        *,
        agent: Agent,
        state: _TinyAgentStreamState,
        baseline_message_count: int,
    ) -> bool:
        _ = (agent, baseline_message_count)
        tool_call_id = event_obj.tool_call_id
        tool_name = event_obj.tool_name
        duration_ms = self._resolve_tool_duration_ms(state, tool_call_id=tool_call_id)
        canonical_result = canonicalize_tool_result(
            event_obj.result,
            tool_name=tool_name,
            is_error=event_obj.is_error,
        )
        result_text = extract_tool_result_text(event_obj.result)
        status = "failed" if event_obj.is_error else "completed"

        if event_obj.is_error:
            state.runtime.tool_registry.fail(
                tool_call_id,
                error=result_text,
                result=canonical_result,
            )
        else:
            state.runtime.tool_registry.complete(tool_call_id, result=canonical_result)

        state.active_tool_call_ids.discard(tool_call_id)
        self._clear_tool_batch_state_if_idle(state)

        if self.tool_result_callback is None:
            return False

        callback_args = state.runtime.tool_registry.get_args(tool_call_id)
        self.tool_result_callback(
            tool_name,
            status,
            callback_args,
            event_obj.result,
            duration_ms,
        )
        return False

    async def _handle_stream_tool_execution_update(
        self,
        event_obj: ToolExecutionUpdateEvent,
        *,
        agent: Agent,
        state: _TinyAgentStreamState,
        baseline_message_count: int,
    ) -> bool:
        _ = (agent, baseline_message_count)
        if self.tool_result_callback is None:
            return False

        tool_call_id = event_obj.tool_call_id
        if event_obj.args is not None:
            callback_args = event_obj.args
        else:
            try:
                callback_args = state.runtime.tool_registry.get_args(tool_call_id)
            except ValueError:
                callback_args = {}
        self.tool_result_callback(
            event_obj.tool_name,
            "running",
            callback_args,
            event_obj.partial_result,
            None,
        )
        return False

    async def _handle_stream_agent_end(
        self,
        event_obj: AgentEndEvent,
        *,
        agent: Agent,
        state: _TinyAgentStreamState,
        baseline_message_count: int,
    ) -> bool:
        _ = (event_obj, state)
        self._persist_agent_messages(agent, baseline_message_count)
        return True

    async def _dispatch_stream_event(
        self,
        *,
        event: AgentEvent,
        agent: Agent,
        state: _TinyAgentStreamState,
        max_iterations: int,
        baseline_message_count: int,
    ) -> bool:
        if is_turn_end_event(event):
            return await self._handle_stream_turn_end(
                event,
                agent=agent,
                state=state,
                max_iterations=max_iterations,
                baseline_message_count=baseline_message_count,
            )
        if isinstance(event, MessageUpdateEvent):
            return await self._handle_stream_message_update(
                event,
                agent=agent,
                state=state,
                baseline_message_count=baseline_message_count,
            )
        if is_message_end_event(event):
            return await self._handle_stream_message_end(
                event,
                agent=agent,
                state=state,
                baseline_message_count=baseline_message_count,
            )
        if is_tool_execution_start_event(event):
            return await self._handle_stream_tool_execution_start(
                event,
                agent=agent,
                state=state,
                baseline_message_count=baseline_message_count,
            )
        if isinstance(event, ToolExecutionUpdateEvent):
            return await self._handle_stream_tool_execution_update(
                event,
                agent=agent,
                state=state,
                baseline_message_count=baseline_message_count,
            )
        if is_tool_execution_end_event(event):
            return await self._handle_stream_tool_execution_end(
                event,
                agent=agent,
                state=state,
                baseline_message_count=baseline_message_count,
            )
        if is_agent_end_event(event):
            return await self._handle_stream_agent_end(
                event,
                agent=agent,
                state=state,
                baseline_message_count=baseline_message_count,
            )
        return False

    async def _run_stream(
        self,
        *,
        agent: Agent,
        max_iterations: int,
        baseline_message_count: int,
    ) -> Agent:
        logger = get_logger()
        runtime = self.state_manager.session.runtime
        state = _TinyAgentStreamState(
            runtime=runtime,
            tool_start_times={},
            active_tool_call_ids=set(),
            batch_tool_call_ids=set(),
            last_stable_agent_message_count=len(agent.state.messages),
        )
        self._active_stream_state = state
        started_at = time.perf_counter()
        stream_thread_id = threading.get_ident()
        event_count = 0
        first_event_ms: float | None = None
        last_event_at = started_at
        logger.lifecycle(f"Stream: start thread={stream_thread_id}")
        stream_completed = False
        try:
            async for event in agent.stream(self.message):
                now = time.perf_counter()
                event_count += 1
                event_name = _describe_stream_event(event)
                if first_event_ms is None:
                    first_event_ms = (now - started_at) * MILLISECONDS_PER_SECOND
                    logger.lifecycle(
                        "Stream: "
                        f"first_event type={event_name} "
                        f"since_start={first_event_ms:.1f}ms "
                        f"thread={stream_thread_id}"
                    )
                else:
                    gap_ms = (now - last_event_at) * MILLISECONDS_PER_SECOND
                    if gap_ms >= STREAM_EVENT_GAP_WARN_MS:
                        logger.lifecycle(
                            "Stream: "
                            f"event_gap type={event_name} "
                            f"gap={gap_ms:.1f}ms "
                            f"count={event_count}"
                        )
                last_event_at = now
                should_stop = await self._dispatch_stream_event(
                    event=event,
                    agent=agent,
                    state=state,
                    max_iterations=max_iterations,
                    baseline_message_count=baseline_message_count,
                )
                if should_stop:
                    break
            stream_completed = True
        finally:
            if stream_completed:
                self._active_stream_state = None

        elapsed_ms = (time.perf_counter() - started_at) * MILLISECONDS_PER_SECOND
        if first_event_ms is None:
            end_message = f"Stream: end events={event_count} first_event=none"
        else:
            end_message = f"Stream: end events={event_count} first_event={first_event_ms:.1f}ms"
        logger.lifecycle(end_message)
        logger.lifecycle(f"Request complete ({elapsed_ms:.0f}ms)")

        error_text = self._agent_error_text(agent)
        if error_text and not is_context_overflow_error(error_text):
            raise AgentError(error_text)

        return agent

    async def _handle_message_update(self, event: MessageUpdateEvent) -> None:
        assistant_event = event.assistant_message_event
        if (
            assistant_event is None
            or not isinstance(assistant_event.delta, str)
            or not assistant_event.delta
        ):
            return

        if assistant_event.type == "text_delta":
            self.state_manager.session._debug_raw_stream_accum += assistant_event.delta
            if self.streaming_callback is not None:
                await self.streaming_callback(assistant_event.delta)
            return

        if assistant_event.type == "thinking_delta" and self.thinking_callback is not None:
            await self.thinking_callback(assistant_event.delta)

    def _handle_abort_cleanup(
        self,
        logger: LogManager,
        *,
        agent: Agent | None = None,
        baseline_message_count: int | None = None,
        invalidate_cache: bool = False,
    ) -> None:
        if agent is not None and baseline_message_count is not None:
            self._rollback_to_last_stable_turn(
                logger,
                agent=agent,
                baseline_message_count=baseline_message_count,
            )

        self._remove_in_flight_tool_registry_entries(logger)
        self._append_interrupted_partial_message()
        self._active_stream_state = None
        if invalidate_cache and ac.invalidate_agent_cache(self.model, self.state_manager):
            logger.lifecycle("Agent cache invalidated after abort")


def get_agent_tool() -> tuple[type[Agent], type[object]]:
    """Return the (Agent, AgentTool) classes."""
    return Agent, cast(type[object], AgentTool)


async def process_request(
    message: str,
    model: ModelName,
    state_manager: StateManagerProtocol,
    streaming_callback: StreamingCallback | None = None,
    thinking_callback: StreamingCallback | None = None,
    tool_result_callback: ToolResultCallback | None = None,
    tool_start_callback: ToolStartCallback | None = None,
    notice_callback: NoticeCallback | None = None,
    compaction_status_callback: CompactionStatusCallback | None = None,
) -> Agent:
    orchestrator = RequestOrchestrator(
        message,
        model,
        state_manager,
        streaming_callback,
        thinking_callback,
        tool_result_callback,
        tool_start_callback,
        notice_callback,
        compaction_status_callback,
    )
    return await orchestrator.run()
