"""Module: tunacode.core.agents.main

Refactored main agent functionality with focused responsibility classes.
Handles agent creation, configuration, and request processing.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool  # noqa: F401

from tunacode.constants import UI_COLORS
from tunacode.core.agents.resume import prune_old_tool_outputs
from tunacode.core.agents.resume.sanitize import (
    find_dangling_tool_call_ids,
    log_message_history_debug,
    remove_consecutive_requests,
    remove_dangling_tool_calls,
    remove_empty_responses,
    sanitize_history_for_resume,
)
from tunacode.core.logging import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import GlobalRequestTimeoutError, UserAbortError
from tunacode.tools.react import ReactTool
from tunacode.types import (
    AgentRun,
    ModelName,
    NoticeCallback,
    ToolCallback,
    ToolCallId,
)
from tunacode.utils.ui import DotDict

from . import agent_components as ac

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
    forced_react_interval: int = 2
    forced_react_limit: int = 5
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
        state_manager: StateManager,
        notice_callback: NoticeCallback | None,
    ) -> None:
        self.state_manager = state_manager
        self.notice_callback = notice_callback

    def track(self, is_empty: bool) -> None:
        """Track empty response and increment counter if empty."""
        if is_empty:
            current = getattr(self.state_manager.session, "consecutive_empty_responses", 0)
            self.state_manager.session.consecutive_empty_responses = current + 1
        else:
            self.state_manager.session.consecutive_empty_responses = 0

    def should_intervene(self) -> bool:
        """Check if intervention is needed (>= 1 consecutive empty)."""
        return getattr(self.state_manager.session, "consecutive_empty_responses", 0) >= 1

    async def prompt_action(self, message: str, reason: str, iteration: int) -> None:
        """Delegate to agent_components.handle_empty_response."""
        logger = get_logger()
        logger.warning(f"Empty response: {reason}", iteration=iteration)

        # Create a minimal state-like object for compatibility
        class StateProxy:
            def __init__(self, sm: StateManager) -> None:
                self.sm = sm
                self.show_thoughts = bool(getattr(sm.session, "show_thoughts", False))

        state_proxy = StateProxy(self.state_manager)
        notice = await ac.handle_empty_response(message, reason, iteration, state_proxy)
        if self.notice_callback:
            self.notice_callback(notice)
        # Clear after intervention
        self.state_manager.session.consecutive_empty_responses = 0


class IterationManager:
    """Manages iteration tracking."""

    def __init__(self, state_manager: StateManager) -> None:
        self.state_manager = state_manager

    def update_counters(self, iteration: int) -> None:
        """Update session iteration counters."""
        self.state_manager.session.current_iteration = iteration
        self.state_manager.session.iteration_count = iteration


class ReactSnapshotManager:
    """Manages forced react snapshots and guidance injection."""

    def __init__(
        self, state_manager: StateManager, react_tool: ReactTool, config: AgentConfig
    ) -> None:
        self.state_manager = state_manager
        self.react_tool = react_tool
        self.config = config

    def should_snapshot(self, iteration: int) -> bool:
        """Check if snapshot should be taken."""
        if iteration < self.config.forced_react_interval:
            return False
        if iteration % self.config.forced_react_interval != 0:
            return False

        forced_calls = getattr(self.state_manager.session, "react_forced_calls", 0)
        return forced_calls < self.config.forced_react_limit

    async def capture_snapshot(
        self, iteration: int, agent_run_ctx: Any, _show_debug: bool = False
    ) -> None:
        """Capture react snapshot and inject guidance."""
        logger = get_logger()
        if not self.should_snapshot(iteration):
            return

        try:
            await self.react_tool.execute(
                action="think",
                thoughts=f"Auto snapshot after iteration {iteration}",
                next_action="continue",
            )

            # Increment forced calls counter
            forced_calls = getattr(self.state_manager.session, "react_forced_calls", 0)
            self.state_manager.session.react_forced_calls = forced_calls + 1

            # Build guidance from last tool call
            timeline = self.state_manager.session.react_scratchpad.get("timeline", [])
            latest = timeline[-1] if timeline else {"thoughts": "?", "next_action": "?"}
            summary = latest.get("thoughts", "")

            tool_calls = getattr(self.state_manager.session, "tool_calls", [])
            if tool_calls:
                last_tool = tool_calls[-1]
                tool_name = last_tool.get("tool", "tool")
                args = last_tool.get("args", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (ValueError, TypeError):
                        args = {}

                detail = ""
                if tool_name == "grep" and isinstance(args, dict):
                    pattern = args.get("pattern")
                    detail = (
                        f"Review grep results for pattern '{pattern}'"
                        if pattern
                        else "Review grep results"
                    )
                elif tool_name == "read_file" and isinstance(args, dict):
                    path = args.get("file_path") or args.get("filepath")
                    detail = (
                        f"Extract key notes from {path}" if path else "Summarize read_file output"
                    )
                else:
                    detail = f"Act on {tool_name} findings"
            else:
                detail = "Plan your first lookup"

            guidance_entry = (
                f"React snapshot {forced_calls + 1}/{self.config.forced_react_limit} "
                f"at iteration {iteration}: {summary}. Next: {detail}"
            )

            # Append and trim guidance
            self.state_manager.session.react_guidance.append(guidance_entry)
            if len(self.state_manager.session.react_guidance) > self.config.forced_react_limit:
                self.state_manager.session.react_guidance = (
                    self.state_manager.session.react_guidance[-self.config.forced_react_limit :]
                )

            # CRITICAL: Inject into agent_run.ctx.messages so next LLM call sees guidance
            if agent_run_ctx is not None:
                ctx_messages = getattr(agent_run_ctx, "messages", None)
                if ctx_messages is None:
                    state = getattr(agent_run_ctx, "state", None)
                    if state and hasattr(state, "message_history"):
                        ctx_messages = state.message_history
                    
                if isinstance(ctx_messages, list):
                    ModelRequest, _, SystemPromptPart = ac.get_model_messages()
                    system_part = SystemPromptPart(
                        content=f"[React Guidance] {guidance_entry}",
                        part_kind="system-prompt",
                    )
                    # CLAUDE_ANCHOR[react-system-injection]
                    # Append synthetic system message so LLM receives react guidance next turn
                    ctx_messages.append(ModelRequest(parts=[system_part], kind="request"))

        except Exception as e:
            logger.debug(f"React snapshot failed: {e}")


class RequestOrchestrator:
    """Orchestrates the main request processing loop."""

    def __init__(
        self,
        message: str,
        model: ModelName,
        state_manager: StateManager,
        tool_callback: ToolCallback | None,
        streaming_callback: Callable[[str], Awaitable[None]] | None,
        tool_result_callback: Callable[..., None] | None = None,
        tool_start_callback: Callable[[str], None] | None = None,
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
            forced_react_interval=2,
            forced_react_limit=5,
            debug_metrics=bool(settings.get("debug_metrics", False)),
        )

        # Initialize managers
        self.empty_handler = EmptyResponseHandler(state_manager, notice_callback)
        self.iteration_manager = IterationManager(state_manager)
        self.react_manager = ReactSnapshotManager(
            state_manager, ReactTool(state_manager=state_manager), self.config
        )

    def _init_request_context(self) -> RequestContext:
        """Initialize request context with ID and config."""
        req_id = str(uuid.uuid4())[:8]
        self.state_manager.session.request_id = req_id

        return RequestContext(
            request_id=req_id,
            max_iterations=self.config.max_iterations,
            debug_metrics=self.config.debug_metrics,
        )

    def _reset_session_state(self) -> None:
        """Reset/initialize fields needed for a new run."""
        self.state_manager.session.current_iteration = 0
        self.state_manager.session.iteration_count = 0
        self.state_manager.session.tool_calls = []
        self.state_manager.session.tool_call_args_by_id = {}
        self.state_manager.session.react_forced_calls = 0
        self.state_manager.session.react_guidance = []

        # Counter used by other subsystems; initialize if absent
        if not hasattr(self.state_manager.session, "batch_counter"):
            self.state_manager.session.batch_counter = 0

        # Track empty response streaks
        self.state_manager.session.consecutive_empty_responses = 0

        self.state_manager.session.original_query = ""

    def _set_original_query_once(self, query: str) -> None:
        """Set original query if not already set."""
        if not getattr(self.state_manager.session, "original_query", None):
            self.state_manager.session.original_query = query

    def _persist_run_messages(self, agent_run: AgentRun, baseline_message_count: int) -> None:
        """Persist authoritative run messages, preserving external additions."""
        run_messages = list(agent_run.all_messages())
        external_messages = self.state_manager.session.messages[baseline_message_count:]
        merged_messages = [*run_messages, *external_messages]

        self.state_manager.session.messages = merged_messages
        self.state_manager.session.update_token_count()

    async def run(self) -> AgentRun:
        """Run the main request processing loop with optional global timeout."""
        from tunacode.core.agents.agent_components.agent_config import (
            _coerce_global_request_timeout,
        )

        timeout = _coerce_global_request_timeout(self.state_manager)
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
        session_messages = self.state_manager.session.messages
        tool_call_args_by_id = self.state_manager.session.tool_call_args_by_id
        _, tokens_reclaimed = prune_old_tool_outputs(session_messages, self.model)
        if tokens_reclaimed > 0:
            logger.lifecycle(f"History pruned ({tokens_reclaimed} tokens reclaimed)")

        debug_mode = bool(getattr(self.state_manager.session, "debug_mode", False))

        # Message cleanup is iterative because each pass can expose new issues:
        # - Removing dangling tool calls may create consecutive requests
        # - Removing consecutive requests may orphan tool returns, creating new dangling calls
        # Loop until no more changes (transitive closure)
        max_cleanup_iterations = 10
        total_cleanup_applied = False
        dangling_tool_call_ids: set[ToolCallId] = set()

        for cleanup_iteration in range(max_cleanup_iterations):
            any_cleanup = False

            dangling_tool_call_ids = find_dangling_tool_call_ids(session_messages)
            if remove_dangling_tool_calls(
                session_messages,
                tool_call_args_by_id,
                dangling_tool_call_ids,
            ):
                any_cleanup = True
                total_cleanup_applied = True
                logger.lifecycle("Cleaned up dangling tool calls")

            # Remove empty response messages (abort during response generation)
            if remove_empty_responses(session_messages):
                any_cleanup = True
                total_cleanup_applied = True

            # Remove consecutive request messages (caused by abort before model responds)
            # Must run AFTER empty response removal since that can expose consecutive requests
            if remove_consecutive_requests(session_messages):
                any_cleanup = True
                total_cleanup_applied = True

            if not any_cleanup:
                break

            if cleanup_iteration == max_cleanup_iterations - 1:
                logger.warning(
                    f"Message cleanup did not stabilize after {max_cleanup_iterations} iterations"
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
                self.state_manager.session.update_token_count()
                total_cleanup_applied = True

        if total_cleanup_applied:
            self.state_manager.session.update_token_count()

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
            type_names = (
                [type(m).__name__ for m in message_history[:3]]
                if message_history
                else []
            )
            logger.debug(
                f"message_history count={len(message_history)}, types={type_names}"
            )
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
                if debug_mode and hasattr(run_handle, 'ctx'):
                    ctx_messages = getattr(run_handle.ctx, 'messages', None)
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

                    # Force react snapshot
                    show_thoughts = bool(
                        getattr(self.state_manager.session, "show_thoughts", False)
                    )
                    await self.react_manager.capture_snapshot(i, run_handle.ctx, show_thoughts)

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
            if agent_run is not None:
                self._persist_run_messages(agent_run, baseline_message_count)
            # Clean up dangling tool calls to prevent API errors on next request
            cleanup_applied = remove_dangling_tool_calls(
                self.state_manager.session.messages,
                self.state_manager.session.tool_call_args_by_id,
            )
            if cleanup_applied:
                self.state_manager.session.update_token_count()

            # Clean up empty response messages (abort during response generation)
            empty_cleanup = remove_empty_responses(self.state_manager.session.messages)
            if empty_cleanup:
                self.state_manager.session.update_token_count()

            # Clean up consecutive request messages (abort before model responded)
            consecutive_cleanup = remove_consecutive_requests(self.state_manager.session.messages)
            if consecutive_cleanup:
                self.state_manager.session.update_token_count()

            # Invalidate agent cache - HTTP client may be in bad state after abort
            invalidated = ac.invalidate_agent_cache(self.model, self.state_manager)
            if invalidated:
                logger.lifecycle("Agent cache invalidated after abort")
            raise


# Utility functions


async def _finalize_buffered_tasks(
    tool_buffer: ac.ToolBuffer,
    tool_callback: ToolCallback | None,
    state_manager: StateManager,
) -> None:
    """Finalize and execute any buffered read-only tasks."""
    if not tool_callback or not tool_buffer.has_tasks():
        return

    buffered_tasks = tool_buffer.flush()
    task_count = len(buffered_tasks)
    logger = get_logger()
    buffered_message = f"Executing buffered tools (count={task_count})"
    logger.lifecycle(buffered_message, request_id=state_manager.session.request_id)

    # Execute
    await ac.execute_tools_parallel(buffered_tasks, tool_callback)


def _message_has_tool_calls(message: Any) -> bool:
    """Return True if message is a model response containing tool calls."""
    # Check parts for tool-call part_kind
    parts = getattr(message, "parts", [])
    for part in parts:
        if getattr(part, "part_kind", None) == "tool-call":
            return True
    # Check tool_calls attribute
    tool_calls = getattr(message, "tool_calls", [])
    return bool(tool_calls)


def get_agent_tool() -> tuple[type[Agent], type[Tool]]:
    """Return Agent and Tool classes without importing at module load time."""
    from pydantic_ai import Agent as AgentCls
    from pydantic_ai import Tool as ToolCls

    return AgentCls, ToolCls


async def check_query_satisfaction(
    agent: Agent,
    original_query: str,
    response: str,
    state_manager: StateManager,
) -> bool:
    """Legacy hook for compatibility; completion still signaled via DONE marker."""
    return True


async def process_request(
    message: str,
    model: ModelName,
    state_manager: StateManager,
    tool_callback: ToolCallback | None = None,
    streaming_callback: Callable[[str], Awaitable[None]] | None = None,
    tool_result_callback: Callable[..., None] | None = None,
    tool_start_callback: Callable[[str], None] | None = None,
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
