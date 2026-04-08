"""Tinyagent stream event loop and per-event handlers for RequestOrchestrator."""

from __future__ import annotations

import threading
import time

from tinyagent.agent import Agent
from tinyagent.agent_types import (
    AgentEndEvent,
    AgentEvent,
    AssistantMessage,
    MessageEndEvent,
    MessageUpdateEvent,
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

from tunacode.exceptions import AgentError

from tunacode.core.debug.usage_trace import log_usage_update
from tunacode.core.logging.manager import get_logger

from ..helpers import (
    _TinyAgentStreamState,
    canonicalize_tool_result,
    extract_tool_result_text,
    is_context_overflow_error,
    parse_canonical_usage,
)

MILLISECONDS_PER_SECOND = 1000
STREAM_EVENT_GAP_WARN_MS = 250.0


def describe_stream_event(event: AgentEvent) -> str:
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


class RequestStreamMixin:
    """Stream loop and event dispatch mixed into RequestOrchestrator."""

    _active_stream_state: _TinyAgentStreamState | None

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
        )
        self._active_stream_state = state
        started_at = time.perf_counter()
        stream_thread_id = threading.get_ident()
        event_count = 0
        first_event_ms: float | None = None
        last_event_at = started_at
        logger.lifecycle(f"Stream: start thread={stream_thread_id}")
        try:
            async for event in agent.stream(self.message):
                now = time.perf_counter()
                event_count += 1
                event_name = describe_stream_event(event)
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
        finally:
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
