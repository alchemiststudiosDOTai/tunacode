"""Main agent functionality for the tinyagent event-stream orchestrator."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import cast

from tinyagent.agent import Agent, extract_text
from tinyagent.agent_types import (
    AgentMessage,
    AgentTool,
    AssistantMessage,
    CustomAgentMessage,
    JsonObject,
    TextContent,
    ToolResultMessage,
    UserMessage,
)

from tunacode.constants import DEFAULT_CONTEXT_WINDOW
from tunacode.exceptions import (
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
    get_or_create_compaction_controller,
)
from tunacode.core.logging.manager import LogManager, get_logger
from tunacode.core.types.state import StateManagerProtocol

from . import agent_components as ac
from .agent_components.agent_config import _coerce_global_request_timeout, _coerce_max_iterations
from .agent_components.agent_debug_events import (
    log_compaction_outcome,
    log_pre_stream_phases,
)
from .agent_components.stream_events import RequestStreamMixin, _TinyAgentStreamState
from .helpers import (
    CONTEXT_OVERFLOW_FAILURE_NOTICE,
    CONTEXT_OVERFLOW_RETRY_NOTICE,
    coerce_error_text,
    is_context_overflow_error,
)
from .resume import sanitize

REQUEST_ID_LENGTH = 8
MILLISECONDS_PER_SECOND = 1000


def _serialize_agent_messages(messages: list[AgentMessage]) -> list[object]:
    serialized_messages: list[object] = []
    for message in messages:
        serialized_messages.append(cast(JsonObject, message.model_dump(exclude_none=True)))
    return serialized_messages


def _deserialize_agent_messages(raw_messages: list[object]) -> list[AgentMessage]:
    deserialized_messages: list[AgentMessage] = []
    for index, raw_message in enumerate(raw_messages):
        if not isinstance(raw_message, dict):
            raise TypeError(
                "sanitized message must be a dict, "
                f"got {type(raw_message).__name__} at index {index}"
            )
        typed_raw_message = cast(JsonObject, raw_message)
        role = typed_raw_message.get("role")
        if role == "user":
            deserialized_messages.append(UserMessage.model_validate(typed_raw_message))
            continue
        if role == "assistant":
            deserialized_messages.append(AssistantMessage.model_validate(typed_raw_message))
            continue
        if role == "tool_result":
            deserialized_messages.append(ToolResultMessage.model_validate(typed_raw_message))
            continue
        deserialized_messages.append(CustomAgentMessage.model_validate(typed_raw_message))
    return deserialized_messages


class RequestOrchestrator(RequestStreamMixin):
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
        hist_len_before_compact = len(conversation.messages)
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
        log_pre_stream_phases(
            self.state_manager,
            request_id=session.runtime.request_id,
            model=str(self.model),
            get_or_create_agent_ms=agent_duration_ms,
            compaction_ms=compaction_duration_ms,
            replace_messages_ms=replace_messages_duration_ms,
            pre_stream_total_ms=pre_stream_duration_ms,
            hist_len_before_compact=hist_len_before_compact,
            compacted_history_len=len(compacted_history),
            user_message_chars=len(self.message),
        )
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

    async def _compact_history_for_request(self, history: list[AgentMessage]) -> list[AgentMessage]:
        self.compaction_controller.reset_request_state()
        outcome = await self.compaction_controller.check_and_compact(
            history,
            max_tokens=self.state_manager.session.conversation.max_tokens,
            signal=None,
            allow_threshold=True,
        )
        log_compaction_outcome(
            self.state_manager,
            request_id=self.state_manager.session.runtime.request_id,
            status=outcome.status,
            reason=outcome.reason,
            msg_in=len(history),
            msg_out=len(outcome.messages),
        )
        return apply_compaction_messages(self.state_manager, outcome.messages)

    async def _force_compact_history(self, history: list[AgentMessage]) -> list[AgentMessage]:
        outcome = await self.compaction_controller.force_compact(
            history,
            max_tokens=self.state_manager.session.conversation.max_tokens,
            signal=None,
        )
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

    def _sanitize_conversation_after_abort(self, logger: LogManager) -> None:
        session = self.state_manager.session
        serialized_messages = _serialize_agent_messages(session.conversation.messages)
        cleanup_applied, dangling_tool_call_ids = sanitize.run_cleanup_loop(
            serialized_messages,
            session.runtime.tool_registry,
        )
        if cleanup_applied:
            session.conversation.messages = _deserialize_agent_messages(serialized_messages)
            session.conversation.total_tokens = estimate_messages_tokens(
                session.conversation.messages
            )
        if cleanup_applied and dangling_tool_call_ids:
            logger.lifecycle(
                f"Cleaned up {len(dangling_tool_call_ids)} dangling tool call(s) after abort"
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

    def _handle_abort_cleanup(
        self,
        logger: LogManager,
        *,
        agent: Agent | None = None,
        baseline_message_count: int | None = None,
        invalidate_cache: bool = False,
    ) -> None:
        if agent is not None and baseline_message_count is not None:
            self._persist_agent_messages(agent, baseline_message_count)

        self._remove_in_flight_tool_registry_entries(logger)
        self._sanitize_conversation_after_abort(logger)
        self._append_interrupted_partial_message()
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
