"""Main agent functionality for the tinyagent event-stream orchestrator."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import cast

from tinyagent.agent import Agent
from tinyagent.agent_types import AgentMessage, AgentTool

from tunacode.constants import DEFAULT_CONTEXT_WINDOW
from tunacode.exceptions import ContextOverflowError, GlobalRequestTimeoutError
from tunacode.types import (
    ModelName,
    NoticeCallback,
    StreamingCallback,
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
from tunacode.core.logging.manager import get_logger
from tunacode.core.types.state import StateManagerProtocol

from . import agent_components as ac
from .agent_components.agent_config import _coerce_global_request_timeout, _coerce_max_iterations
from .agent_components.agent_streaming import AgentStreamMixin
from .helpers import (
    CONTEXT_OVERFLOW_FAILURE_NOTICE,
    CONTEXT_OVERFLOW_RETRY_NOTICE,
    _TinyAgentStreamState,
    coerce_error_text,
    is_context_overflow_error,
)

REQUEST_ID_LENGTH = 8
MILLISECONDS_PER_SECOND = 1000


class RequestOrchestrator(AgentStreamMixin):
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
