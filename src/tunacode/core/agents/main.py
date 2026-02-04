"""Module: tunacode.core.agents.main

Main agent functionality with focused responsibility classes.
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

from tunacode.core.agents.history_preparer import HistoryPreparer
from tunacode.core.agents.request_logger import log_node_details, log_run_handle_context_messages
from tunacode.core.agents.resume.sanitize import (
    remove_consecutive_requests,
    remove_dangling_tool_calls,
    remove_empty_responses,
)
from tunacode.core.logging import get_logger
from tunacode.core.types import StateManagerProtocol

from . import agent_components as ac

__all__ = [
    "process_request",
    "get_agent_tool",
    "check_query_satisfaction",
]

DEFAULT_MAX_ITERATIONS: int = 15
REQUEST_ID_LENGTH: int = 8
MESSAGE_PREVIEW_LENGTH: int = 50
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
        runtime = self.state_manager.session.runtime
        if is_empty:
            runtime.consecutive_empty_responses += 1
        else:
            runtime.consecutive_empty_responses = 0

    def should_intervene(self) -> bool:
        """Check if intervention is needed (>= 1 consecutive empty)."""
        runtime = self.state_manager.session.runtime
        return runtime.consecutive_empty_responses >= 1

    async def prompt_action(self, message: str, reason: str, iteration: int) -> None:
        """Handle empty response intervention."""
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

        user_config = getattr(state_manager.session, "user_config", {}) or {}
        settings = user_config.get("settings", {})
        self.config = AgentConfig(
            max_iterations=int(settings.get("max_iterations", DEFAULT_MAX_ITERATIONS)),
            debug_metrics=bool(settings.get("debug_metrics", False)),
        )

        self.empty_handler = EmptyResponseHandler(state_manager, notice_callback)
        self.history_preparer = HistoryPreparer(state_manager, model, message)

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
            logger = get_logger()
            invalidated = ac.invalidate_agent_cache(self.model, self.state_manager)
            if invalidated:
                logger.lifecycle("Agent cache invalidated after timeout")
            raise GlobalRequestTimeoutError(timeout) from e

    async def _run_impl(self) -> AgentRun:
        """Internal implementation of request processing loop."""
        ctx = self._initialize_request()
        logger = get_logger()
        logger.info("Request started", request_id=ctx.request_id)

        agent = ac.get_or_create_agent(self.model, self.state_manager)
        message_history, debug_mode, baseline_message_count = self.history_preparer.prepare(logger)
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
        ctx = self._create_request_context()
        self._reset_session_state()
        self._set_original_query_once()
        return ctx

    def _create_request_context(self) -> RequestContext:
        """Create request context with ID and config."""
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
        runtime.current_iteration = 0
        runtime.iteration_count = 0
        runtime.tool_registry.clear()
        runtime.batch_counter = 0
        runtime.consecutive_empty_responses = 0
        session.task.original_query = ""

    def _set_original_query_once(self) -> None:
        """Set original query if not already set."""
        task_state = self.state_manager.session.task
        if not task_state.original_query:
            task_state.original_query = self.message

    def _persist_run_messages(self, agent_run: AgentRun, baseline_message_count: int) -> None:
        """Persist authoritative run messages, preserving external additions."""
        run_messages = list(agent_run.all_messages())
        conversation = self.state_manager.session.conversation
        external_messages = conversation.messages[baseline_message_count:]
        conversation.messages = [*run_messages, *external_messages]

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
                log_run_handle_context_messages(run_handle, logger)

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
        log_node_details(node, logger)

        runtime = self.state_manager.session.runtime
        runtime.current_iteration = iteration_index
        runtime.iteration_count = iteration_index

        is_request_node = Agent.is_model_request_node(node)
        if self.streaming_callback and is_request_node:
            await ac.stream_model_request_node(
                node,
                agent_run_ctx,
                self.state_manager,
                self.streaming_callback,
                request_id,
                iteration_index,
            )

        empty_response, empty_reason = await ac.process_node(
            node,
            self.tool_callback,
            self.state_manager,
            self.streaming_callback,
            response_state,
            self.tool_result_callback,
            self.tool_start_callback,
        )
        iter_elapsed_ms = (time.perf_counter() - iter_start) * MILLISECONDS_PER_SECOND
        logger.lifecycle(f"Iteration {iteration_index} complete ({iter_elapsed_ms:.0f}ms)")

        self.empty_handler.track(empty_response)
        if empty_response and self.empty_handler.should_intervene():
            await self.empty_handler.prompt_action(
                self.message,
                empty_reason or "",
                iteration_index,
            )

        node_output = getattr(getattr(node, "result", None), "output", None)
        if node_output:
            response_state.has_user_response = True

        if response_state.task_completed:
            logger.lifecycle(f"Task completed at iteration {iteration_index}")
            return True

        return False

    def _handle_abort_cleanup(self, logger: Any) -> None:
        """Clean up session state after abort or cancellation."""
        session = self.state_manager.session
        conversation = session.conversation
        runtime = session.runtime

        partial_text = session._debug_raw_stream_accum
        if partial_text.strip():
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
