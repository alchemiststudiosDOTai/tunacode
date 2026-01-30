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


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""

    max_iterations: int = 15
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
            max_iterations=int(settings.get("max_iterations", 15)),
            debug_metrics=bool(settings.get("debug_metrics", False)),
        )

        # Initialize managers
        self.empty_handler = EmptyResponseHandler(state_manager, notice_callback)
        self.iteration_manager = IterationManager(state_manager)

    def _init_request_context(self) -> RequestContext:
        """Initialize request context with ID and config."""
        req_id = str(uuid.uuid4())[:8]
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
        self.state_manager.session.update_token_count()

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
        ctx = self._init_request_context()
        self._reset_session_state()
        self._set_original_query_once(self.message)

        logger = get_logger()
        request_id = ctx.request_id
        logger.info("Request started", request_id=request_id)

        # Acquire agent
        agent = ac.get_or_create_agent(self.model, self.state_manager)

        # Prune old tool outputs directly in session (persisted)
        session = self.state_manager.session
        conversation = session.conversation
        runtime = session.runtime
        session_messages = conversation.messages
        tool_registry = runtime.tool_registry
        _, tokens_reclaimed = prune_old_tool_outputs(session_messages, self.model)
        if tokens_reclaimed > 0:
            logger.lifecycle(f"History pruned ({tokens_reclaimed} tokens reclaimed)")

        debug_mode = bool(getattr(session, "debug_mode", False))

        # Run iterative cleanup until message history stabilizes
        total_cleanup_applied, dangling_tool_call_ids = run_cleanup_loop(
            session_messages, tool_registry
        )

        # Handle trailing request in history if we are about to add a new one.
        # This prevents [Request, Request] sequences when resuming after an abort.
        # Only do this if we have a non-empty message (intent to start new turn).
        if session_messages and self.message:
            last_msg = session_messages[-1]
            # Check for pydantic-ai ModelRequest or dict with kind='request'
            last_kind = getattr(last_msg, "kind", None)
            if isinstance(last_msg, dict):
                last_kind = last_msg.get("kind")

            if last_kind == "request":
                logger.lifecycle("Dropping trailing request to avoid consecutive requests")
                session_messages.pop()
                session.update_token_count()
                total_cleanup_applied = True

        if total_cleanup_applied:
            session.update_token_count()

        if debug_mode:
            log_message_history_debug(
                session_messages,
                self.message,
                dangling_tool_call_ids,
            )

        baseline_message_count = len(session_messages)

        # Debug: Log message history state for diagnosing abort-related corruption
        if session_messages:
            last_msg = session_messages[-1]
            last_kind = getattr(last_msg, "kind", "unknown")
            last_parts_count = len(getattr(last_msg, "parts", []))
            has_tool_calls = _message_has_tool_calls(last_msg)
            logger.debug(
                f"History state: {baseline_message_count} messages, "
                f"last_kind={last_kind}, parts={last_parts_count}, "
                f"has_tool_calls={has_tool_calls}"
            )

            # Detailed: log last 3 messages for debugging corrupt history
            for idx, msg in enumerate(session_messages[-3:]):
                msg_kind = getattr(msg, "kind", "?")
                msg_parts = getattr(msg, "parts", [])
                parts_summary = []
                for p in msg_parts[:5]:  # limit to first 5 parts
                    p_kind = getattr(p, "part_kind", "?")
                    p_content = getattr(p, "content", None)
                    content_preview = ""
                    if isinstance(p_content, str):
                        content_preview = f":{len(p_content)}chars"
                    parts_summary.append(f"{p_kind}{content_preview}")
                logger.debug(
                    f"  msg[-{3 - idx}]: kind={msg_kind}, parts=[{', '.join(parts_summary)}]"
                )

        # Prepare history snapshot (now pruned)
        # Sanitize history to prevent run_id conflicts or stale state on resume
        message_history = sanitize_history_for_resume(session_messages)

        # CRITICAL DEBUG: Verify message_history state before passing to agent.iter()
        if debug_mode:
            type_names = [type(m).__name__ for m in message_history[:3]] if message_history else []
            logger.debug(f"message_history count={len(message_history)}, types={type_names}")
            if message_history:
                logger.debug(
                    f"message_history[0]: {type(message_history[0]).__name__} "
                    f"kind={getattr(message_history[0], 'kind', 'unknown')}"
                )
                if len(message_history) > 1:
                    logger.debug(
                        f"message_history[-1]: {type(message_history[-1]).__name__} "
                        f"kind={getattr(message_history[-1], 'kind', 'unknown')}"
                    )

        # Per-request trackers
        tool_buffer = ac.ToolBuffer()
        response_state = ac.ResponseState()
        agent_run: AgentRun | None = None

        try:
            msg_preview = self.message[:50]
            history_len = len(message_history)
            logger.debug(f"Starting agent.iter(): msg={msg_preview}... history={history_len}")
            async with agent.iter(self.message, message_history=message_history) as run_handle:
                logger.debug("agent.iter() context entered successfully")
                agent_run = run_handle

                # CRITICAL DEBUG: Check if pydantic-ai received the message_history
                if debug_mode and hasattr(run_handle, "ctx"):
                    ctx_messages = getattr(run_handle.ctx, "messages", None)
                    if ctx_messages is None:
                        run_state = getattr(run_handle.ctx, "state", None)
                        if run_state and hasattr(run_state, "message_history"):
                            ctx_messages = run_state.message_history

                    if ctx_messages is not None:
                        logger.debug(f"pydantic-ai ctx.messages count={len(ctx_messages)}")
                        if ctx_messages:
                            logger.debug(f"ctx.messages[0] type={type(ctx_messages[0]).__name__}")
                    else:
                        logger.debug("pydantic-ai ctx.messages not found or None")
                i = 1
                async for node in run_handle:
                    iter_start = time.perf_counter()
                    logger.lifecycle(f"--- Iteration {i} ---")

                    # Debug: Log node type and key attributes for diagnosing hangs
                    node_type = type(node).__name__
                    has_request = getattr(node, "request", None) is not None
                    has_response = getattr(node, "model_response", None) is not None
                    has_thought = getattr(node, "thought", None) is not None
                    logger.debug(
                        f"Node: type={node_type}, "
                        f"has_request={has_request}, has_response={has_response}, "
                        f"has_thought={has_thought}"
                    )

                    self.iteration_manager.update_counters(i)

                    # Stream tokens from model request nodes
                    if self.streaming_callback and Agent.is_model_request_node(node):
                        await ac.stream_model_request_node(
                            node,
                            agent_run.ctx,
                            self.state_manager,
                            self.streaming_callback,
                            ctx.request_id,
                            i,
                        )

                    # Core node processing
                    empty_response, empty_reason = await ac.process_node(
                        node,
                        self.tool_callback,
                        self.state_manager,
                        tool_buffer,
                        self.streaming_callback,
                        response_state,
                        self.tool_result_callback,
                        self.tool_start_callback,
                    )
                    iter_elapsed_ms = (time.perf_counter() - iter_start) * 1000
                    logger.lifecycle(f"Iteration {i} complete ({iter_elapsed_ms:.0f}ms)")

                    # Handle empty response
                    self.empty_handler.track(empty_response)
                    if empty_response and self.empty_handler.should_intervene():
                        await self.empty_handler.prompt_action(self.message, empty_reason or "", i)

                    # Track whether we produced visible user output this iteration
                    if getattr(getattr(node, "result", None), "output", None):
                        response_state.has_user_response = True

                    # Early completion
                    if response_state.task_completed:
                        logger.lifecycle(f"Task completed at iteration {i}")
                        break

                    i += 1

                await _finalize_buffered_tasks(
                    tool_buffer,
                    self.tool_callback,
                    self.state_manager,
                )

                # Return wrapper that carries response_state
                self._persist_run_messages(run_handle, baseline_message_count)
                logger.lifecycle("Request complete")
                return ac.AgentRunWithState(run_handle, response_state)

        except (UserAbortError, asyncio.CancelledError):
            # DON'T persist agent_run messages - they contain the dangling tool call
            # Just clean up what's already in conversation messages
            session = self.state_manager.session
            conversation = session.conversation
            runtime = session.runtime

            # Capture partial response before cleanup
            partial_text = session._debug_raw_stream_accum
            if partial_text.strip():
                from pydantic_ai.messages import ModelResponse, TextPart

                partial_msg = ModelResponse(
                    parts=[TextPart(content=f"[INTERRUPTED]\n\n{partial_text}")]
                )
                conversation.messages.append(partial_msg)
                session.update_token_count()

            cleanup_applied = remove_dangling_tool_calls(
                conversation.messages,
                runtime.tool_registry,
            )
            if cleanup_applied:
                session.update_token_count()

            # Clean up empty response messages (abort during response generation)
            empty_cleanup = remove_empty_responses(conversation.messages)
            if empty_cleanup:
                session.update_token_count()

            # Clean up consecutive request messages (abort before model responded)
            consecutive_cleanup = remove_consecutive_requests(conversation.messages)
            if consecutive_cleanup:
                session.update_token_count()

            # Invalidate agent cache - HTTP client may be in bad state after abort
            invalidated = ac.invalidate_agent_cache(self.model, self.state_manager)
            if invalidated:
                logger.lifecycle("Agent cache invalidated after abort")
            raise


# Utility functions


async def _finalize_buffered_tasks(
    tool_buffer: ac.ToolBuffer,
    tool_callback: ToolCallback | None,
    state_manager: StateManagerProtocol,
) -> None:
    """Finalize and execute any buffered read-only tasks."""
    if not tool_callback or not tool_buffer.has_tasks():
        return

    buffered_tasks = tool_buffer.flush()
    task_count = len(buffered_tasks)
    logger = get_logger()
    buffered_message = f"Executing buffered tools (count={task_count})"
    request_id = state_manager.session.runtime.request_id
    logger.lifecycle(buffered_message, request_id=request_id)

    # Execute
    await ac.execute_tools_parallel(buffered_tasks, tool_callback)


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
