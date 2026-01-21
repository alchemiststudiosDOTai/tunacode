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
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool  # noqa: F401

from tunacode.constants import UI_COLORS
from tunacode.core.compaction import prune_old_tool_outputs
from tunacode.core.logging import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import GlobalRequestTimeoutError, UserAbortError
from tunacode.tools.react import ReactTool
from tunacode.types import (
    AgentRun,
    ModelName,
    NoticeCallback,
    ToolArgs,
    ToolCallback,
    ToolCallId,
)
from tunacode.utils.ui import DotDict

from . import agent_components as ac

colors = DotDict(UI_COLORS)

PART_KIND_TOOL_CALL: str = "tool-call"
PART_KIND_TOOL_RETURN: str = "tool-return"
PART_KIND_ATTR: str = "part_kind"
PARTS_ATTR: str = "parts"
TOOL_CALLS_ATTR: str = "tool_calls"
TOOL_CALL_ID_ATTR: str = "tool_call_id"
DANGLING_TOOL_CALLS_CLEANUP_MESSAGE: str = "Dangling tool calls removed before request"
DEBUG_PREVIEW_SUFFIX: str = "..."
DEBUG_NEWLINE_REPLACEMENT: str = "\\n"
DEBUG_HISTORY_MESSAGE_PREVIEW_LEN: int = 160
DEBUG_HISTORY_PART_PREVIEW_LEN: int = 120
STREAM_WATCHDOG_DEFAULT_SECONDS: float = 20.0
STREAM_WATCHDOG_MIN_SECONDS: float = 5.0
STREAM_WATCHDOG_MAX_SECONDS: float = 45.0
STREAM_WATCHDOG_FRACTION: float = 0.25
STREAM_WATCHDOG_GLOBAL_FALLBACK: float = 120.0

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

            dangling_tool_call_ids = _find_dangling_tool_call_ids(session_messages)
            if _remove_dangling_tool_calls(
                session_messages,
                tool_call_args_by_id,
                dangling_tool_call_ids,
            ):
                any_cleanup = True
                total_cleanup_applied = True
                logger.lifecycle("Cleaned up dangling tool calls")

            # Remove empty response messages (abort during response generation)
            if _remove_empty_responses(session_messages):
                any_cleanup = True
                total_cleanup_applied = True

            # Remove consecutive request messages (caused by abort before model responds)
            # Must run AFTER empty response removal since that can expose consecutive requests
            if _remove_consecutive_requests(session_messages):
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
            _log_message_history_debug(
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
        message_history = _sanitize_history_for_resume(session_messages)

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

                    # Optional token streaming
                    await _maybe_stream_node_tokens(
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
                        await self.empty_handler.prompt_action(self.message, empty_reason, i)

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
            cleanup_applied = _remove_dangling_tool_calls(
                self.state_manager.session.messages,
                self.state_manager.session.tool_call_args_by_id,
            )
            if cleanup_applied:
                self.state_manager.session.update_token_count()

            # Clean up empty response messages (abort during response generation)
            empty_cleanup = _remove_empty_responses(self.state_manager.session.messages)
            if empty_cleanup:
                self.state_manager.session.update_token_count()

            # Clean up consecutive request messages (abort before model responded)
            consecutive_cleanup = _remove_consecutive_requests(self.state_manager.session.messages)
            if consecutive_cleanup:
                self.state_manager.session.update_token_count()

            # Invalidate agent cache - HTTP client may be in bad state after abort
            invalidated = ac.invalidate_agent_cache(self.model, self.state_manager)
            if invalidated:
                logger.lifecycle("Agent cache invalidated after abort")
            raise


# Utility functions


def _coerce_stream_watchdog_timeout(state_manager: StateManager) -> float:
    """Compute stream watchdog timeout based on global request timeout."""
    settings = state_manager.session.user_config.get("settings", {})
    global_timeout_raw = settings.get(
        "global_request_timeout",
        STREAM_WATCHDOG_GLOBAL_FALLBACK,
    )

    try:
        global_timeout = float(global_timeout_raw)
    except (TypeError, ValueError):
        return STREAM_WATCHDOG_DEFAULT_SECONDS

    if global_timeout <= 0:
        return STREAM_WATCHDOG_DEFAULT_SECONDS

    stream_timeout = global_timeout * STREAM_WATCHDOG_FRACTION
    stream_timeout = min(stream_timeout, STREAM_WATCHDOG_MAX_SECONDS)
    stream_timeout = max(stream_timeout, STREAM_WATCHDOG_MIN_SECONDS)
    return stream_timeout


async def _maybe_stream_node_tokens(
    node: Any,
    agent_run_ctx: Any,
    state_manager: StateManager,
    streaming_cb: Callable[[str], Awaitable[None]] | None,
    request_id: str,
    iteration_index: int,
) -> None:
    """Stream tokens from model request nodes if callback provided.

    Reference: main.py lines 146-161
    """
    if not streaming_cb:
        return

    # Delegate to component streaming helper
    if Agent.is_model_request_node(node):  # type: ignore[attr-defined]
        logger = get_logger()
        stream_timeout = _coerce_stream_watchdog_timeout(state_manager)
        debug_mode = bool(getattr(state_manager.session, "debug_mode", False))
        try:
            await asyncio.wait_for(
                ac.stream_model_request_node(
                    node,
                    agent_run_ctx,
                    state_manager,
                    streaming_cb,
                    request_id,
                    iteration_index,
                ),
                timeout=stream_timeout,
            )
        except TimeoutError:
            logger.warning(
                f"Stream watchdog timeout after {stream_timeout:.1f}s; "
                "falling back to non-streaming"
            )
            logger.lifecycle(f"Stream watchdog timeout ({stream_timeout:.1f}s)")
            if debug_mode:
                logger.debug(
                    f"Stream watchdog abort: request_id={request_id} iteration={iteration_index}"
                )
            try:
                if hasattr(node, "_did_stream"):
                    node._did_stream = False
            except Exception:
                pass


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
    tool_call_ids = _collect_message_tool_call_ids(message)
    return bool(tool_call_ids)


def _get_attr_value(item: Any, attr_name: str) -> Any:
    """Return attribute values from dicts or objects."""
    if isinstance(item, dict):
        return item.get(attr_name)
    return getattr(item, attr_name, None)


def _normalize_list(value: Any) -> list[Any]:
    """Normalize optional list-like values to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _get_message_parts(message: Any) -> list[Any]:
    """Return message parts as a list."""
    parts_value = _get_attr_value(message, PARTS_ATTR)
    return _normalize_list(parts_value)


def _set_message_parts(message: Any, parts: list[Any]) -> None:
    """Assign new parts to a message."""
    if isinstance(message, dict):
        message[PARTS_ATTR] = parts
        return
    if hasattr(message, PARTS_ATTR):
        setattr(message, PARTS_ATTR, parts)


def _get_message_tool_calls(message: Any) -> list[Any]:
    """Return tool_calls from a message as a list."""
    tool_calls_value = _get_attr_value(message, TOOL_CALLS_ATTR)
    return _normalize_list(tool_calls_value)


def _set_message_tool_calls(message: Any, tool_calls: list[Any]) -> None:
    """Assign tool_calls to a message.

    Note: For pydantic-ai messages, tool_calls is a read-only property derived
    from parts. Setting parts is sufficient; this function only handles dict
    messages (e.g., serialized session data).
    """
    if isinstance(message, dict):
        message[TOOL_CALLS_ATTR] = tool_calls
        return
    # For pydantic-ai message objects, tool_calls is a computed property
    # derived from parts. We cannot set it directly - setting parts is enough.


def _format_debug_preview(value: Any, max_len: int) -> tuple[str, int]:
    """Format a debug preview with length metadata."""
    if value is None:
        return "", 0

    value_text = value if isinstance(value, str) else str(value)
    value_len = len(value_text)
    preview_len = min(max_len, value_len)
    preview_text = value_text[:preview_len]
    if value_len > preview_len:
        preview_text = f"{preview_text}{DEBUG_PREVIEW_SUFFIX}"
    preview_text = preview_text.replace("\n", DEBUG_NEWLINE_REPLACEMENT)
    return preview_text, value_len


def _format_part_debug(part: Any, max_len: int) -> str:
    """Format a single part for debug logging."""
    part_kind_value = _get_attr_value(part, PART_KIND_ATTR)
    part_kind = part_kind_value if part_kind_value is not None else "unknown"
    tool_name = _get_attr_value(part, "tool_name")
    tool_call_id = _get_attr_value(part, TOOL_CALL_ID_ATTR)
    content = _get_attr_value(part, "content")
    args = _get_attr_value(part, "args")

    segments = [f"kind={part_kind}"]
    if tool_name:
        segments.append(f"tool={tool_name}")
    if tool_call_id:
        segments.append(f"id={tool_call_id}")

    content_preview, content_len = _format_debug_preview(content, max_len)
    if content_preview:
        segments.append(f"content={content_preview} ({content_len} chars)")

    args_preview, args_len = _format_debug_preview(args, max_len)
    if args_preview:
        segments.append(f"args={args_preview} ({args_len} chars)")

    return " ".join(segments)


def _format_tool_call_debug(tool_call: Any, max_len: int) -> str:
    """Format a tool call metadata entry for debug logging."""
    tool_name = _get_attr_value(tool_call, "tool_name")
    tool_call_id = _get_attr_value(tool_call, TOOL_CALL_ID_ATTR)
    args = _get_attr_value(tool_call, "args")

    segments: list[str] = []
    if tool_name:
        segments.append(f"tool={tool_name}")
    if tool_call_id:
        segments.append(f"id={tool_call_id}")

    args_preview, args_len = _format_debug_preview(args, max_len)
    if args_preview:
        segments.append(f"args={args_preview} ({args_len} chars)")

    if not segments:
        segments.append("empty")

    return " ".join(segments)


def _collect_tool_call_ids_from_parts(parts: list[Any]) -> list[ToolCallId]:
    """Collect tool_call_id values from tool-call parts."""
    if not parts:
        return []

    tool_call_ids: list[ToolCallId] = []
    for part in parts:
        part_kind = _get_attr_value(part, PART_KIND_ATTR)
        if part_kind != PART_KIND_TOOL_CALL:
            continue
        tool_call_id = _get_attr_value(part, TOOL_CALL_ID_ATTR)
        if tool_call_id is None:
            continue
        tool_call_ids.append(tool_call_id)
    return tool_call_ids


def _collect_tool_call_ids_from_tool_calls(tool_calls: list[Any]) -> list[ToolCallId]:
    """Collect tool_call_id values from tool_calls lists."""
    if not tool_calls:
        return []

    tool_call_ids: list[ToolCallId] = []
    for tool_call in tool_calls:
        tool_call_id = _get_attr_value(tool_call, TOOL_CALL_ID_ATTR)
        if tool_call_id is None:
            continue
        tool_call_ids.append(tool_call_id)
    return tool_call_ids


def _collect_tool_return_ids_from_parts(parts: list[Any]) -> list[ToolCallId]:
    """Collect tool_call_id values from tool-return parts."""
    if not parts:
        return []

    tool_return_ids: list[ToolCallId] = []
    for part in parts:
        part_kind = _get_attr_value(part, PART_KIND_ATTR)
        if part_kind != PART_KIND_TOOL_RETURN:
            continue
        tool_call_id = _get_attr_value(part, TOOL_CALL_ID_ATTR)
        if tool_call_id is None:
            continue
        tool_return_ids.append(tool_call_id)
    return tool_return_ids


def _collect_message_tool_call_ids(message: Any) -> set[ToolCallId]:
    """Collect tool_call_ids from tool-call parts and tool_calls metadata."""
    parts = _get_message_parts(message)
    tool_calls = _get_message_tool_calls(message)

    tool_call_ids = set(_collect_tool_call_ids_from_parts(parts))
    tool_call_ids.update(_collect_tool_call_ids_from_tool_calls(tool_calls))
    return tool_call_ids


def _collect_message_tool_return_ids(message: Any) -> set[ToolCallId]:
    """Collect tool_call_ids from tool-return parts."""
    parts = _get_message_parts(message)
    return set(_collect_tool_return_ids_from_parts(parts))


def _find_dangling_tool_call_ids(messages: list[Any]) -> set[ToolCallId]:
    """Return tool_call_ids that never received a tool return."""
    if not messages:
        return set()

    tool_call_ids: set[ToolCallId] = set()
    tool_return_ids: set[ToolCallId] = set()

    for message in messages:
        tool_call_ids.update(_collect_message_tool_call_ids(message))
        tool_return_ids.update(_collect_message_tool_return_ids(message))

    return tool_call_ids - tool_return_ids


MESSAGE_KIND_REQUEST = "request"
MESSAGE_KIND_RESPONSE = "response"


def _remove_consecutive_requests(messages: list[Any]) -> bool:
    """Remove consecutive request messages, keeping only the last in each run.

    The API expects alternating request/response messages. When abort happens
    before model responds, we can end up with consecutive request messages.
    This function removes all but the last request in any consecutive run.

    Returns:
        True if any messages were removed, False otherwise.
    """
    if len(messages) < 2:
        return False

    logger = get_logger()
    indices_to_remove: list[int] = []
    i = 0

    while i < len(messages) - 1:
        current_kind = getattr(messages[i], "kind", None)

        if current_kind != MESSAGE_KIND_REQUEST:
            i += 1
            continue

        # Found a request - check if next message is also a request
        run_start = i
        while i < len(messages) - 1:
            next_kind = getattr(messages[i + 1], "kind", None)
            if next_kind != MESSAGE_KIND_REQUEST:
                break
            i += 1

        # If we advanced, we have consecutive requests from run_start to i
        # Keep only the last one (at index i), remove run_start to i-1
        if i > run_start:
            for idx in range(run_start, i):
                indices_to_remove.append(idx)

        i += 1

    if not indices_to_remove:
        return False

    # Remove in reverse order to preserve indices
    for idx in reversed(indices_to_remove):
        removed_msg = messages[idx]
        removed_kind = getattr(removed_msg, "kind", "unknown")
        removed_parts = len(getattr(removed_msg, "parts", []))
        logger.debug(
            f"Removing consecutive request at index {idx}: "
            f"kind={removed_kind} parts={removed_parts}"
        )
        del messages[idx]

    logger.lifecycle(f"Removed {len(indices_to_remove)} consecutive request messages")
    return True


def _remove_empty_responses(messages: list[Any]) -> bool:
    """Remove response messages with zero parts.

    Empty responses (parts=0) can occur when abort happens after model starts
    responding but before any content is generated. These empty responses
    create invalid message sequences.

    Returns:
        True if any messages were removed, False otherwise.
    """
    if not messages:
        return False

    logger = get_logger()
    indices_to_remove: list[int] = []

    for i, message in enumerate(messages):
        msg_kind = getattr(message, "kind", None)
        if msg_kind != MESSAGE_KIND_RESPONSE:
            continue

        parts = getattr(message, "parts", [])
        if not parts:
            indices_to_remove.append(i)

    if not indices_to_remove:
        return False

    for idx in reversed(indices_to_remove):
        logger.debug(f"Removing empty response at index {idx}")
        del messages[idx]

    logger.lifecycle(f"Removed {len(indices_to_remove)} empty response messages")
    return True


PART_KIND_SYSTEM_PROMPT: str = "system-prompt"


def _strip_system_prompt_parts(parts: list[Any]) -> list[Any]:
    """Remove system-prompt parts from a list of message parts.

    pydantic-ai injects the system prompt automatically via agent.system_prompt.
    If message_history contains system prompts from a previous run, we get
    duplicate system prompts which can confuse the model or cause hangs.
    """
    if not parts:
        return parts

    return [p for p in parts if _get_attr_value(p, PART_KIND_ATTR) != PART_KIND_SYSTEM_PROMPT]


def _sanitize_history_for_resume(messages: list[Any]) -> list[Any]:
    """Sanitize message history to ensure compatibility with pydantic-ai.

    This function:
    1. Removes internal IDs (run_id) that bind messages to previous sessions
    2. Strips system-prompt parts (pydantic-ai injects these automatically)
    3. Removes empty messages that result from stripping

    Critical: pydantic-ai v1.21.0+ enforces that agent.iter() adds its own
    system prompt. If history contains system prompts, they will be duplicated.
    """
    if not messages:
        return []

    sanitized = []
    logger = get_logger()
    system_prompts_stripped = 0

    for msg in messages:
        # Handle dict messages (from serialization)
        if isinstance(msg, dict):
            msg_copy = msg.copy()
            if PARTS_ATTR in msg_copy and isinstance(msg_copy[PARTS_ATTR], list):
                original_count = len(msg_copy[PARTS_ATTR])
                msg_copy[PARTS_ATTR] = _strip_system_prompt_parts(msg_copy[PARTS_ATTR])
                system_prompts_stripped += original_count - len(msg_copy[PARTS_ATTR])
                # Skip empty messages
                if not msg_copy[PARTS_ATTR]:
                    continue
            sanitized.append(msg_copy)
            continue

        # Handle pydantic-ai message objects
        parts = _get_message_parts(msg)
        original_part_count = len(parts)
        filtered_parts = _strip_system_prompt_parts(parts)
        stripped_count = original_part_count - len(filtered_parts)
        system_prompts_stripped += stripped_count

        # Skip messages that become empty after stripping system prompts
        if original_part_count > 0 and not filtered_parts:
            continue

        # Clean run_id and update parts if needed
        try:
            if hasattr(msg, "run_id"):
                if stripped_count > 0:
                    clean_msg = replace(msg, run_id=None, parts=filtered_parts)
                else:
                    clean_msg = replace(msg, run_id=None)
                sanitized.append(clean_msg)
            elif stripped_count > 0:
                # No run_id but need to update parts
                clean_msg = replace(msg, parts=filtered_parts)
                sanitized.append(clean_msg)
            else:
                sanitized.append(msg)
        except Exception as e:
            logger.debug(f"Failed to sanitize message {type(msg).__name__}: {e}")
            sanitized.append(msg)

    if system_prompts_stripped > 0:
        logger.lifecycle(f"Stripped {system_prompts_stripped} system-prompt parts from history")

    return sanitized


def _log_message_history_debug(
    messages: list[Any],
    user_message: str,
    dangling_tool_call_ids: set[ToolCallId],
) -> None:
    """Log a detailed history snapshot for debug tracing."""
    logger = get_logger()
    message_count = len(messages)
    dangling_count = len(dangling_tool_call_ids)
    logger.debug(f"History dump: messages={message_count} dangling_tool_calls={dangling_count}")

    if dangling_tool_call_ids:
        dangling_sorted = sorted(dangling_tool_call_ids)
        logger.debug(f"History dangling tool_call_ids: {dangling_sorted}")

    if user_message:
        preview, msg_len = _format_debug_preview(
            user_message,
            DEBUG_HISTORY_MESSAGE_PREVIEW_LEN,
        )
        logger.debug(f"Outgoing user message: {preview} ({msg_len} chars)")

    for msg_index, message in enumerate(messages):
        msg_kind_value = _get_attr_value(message, "kind")
        msg_kind = msg_kind_value if msg_kind_value is not None else "unknown"
        parts = _get_message_parts(message)
        tool_calls = _get_message_tool_calls(message)
        tool_call_ids = _collect_message_tool_call_ids(message)
        tool_return_ids = _collect_message_tool_return_ids(message)

        part_count = len(parts)
        tool_call_count = len(tool_call_ids)
        tool_return_count = len(tool_return_ids)

        summary = (
            f"history[{msg_index}] kind={msg_kind} "
            f"parts={part_count} tool_calls={tool_call_count} "
            f"tool_returns={tool_return_count}"
        )
        if tool_call_ids:
            tool_call_sorted = sorted(tool_call_ids)
            summary = f"{summary} tool_call_ids={tool_call_sorted}"
        if tool_return_ids:
            tool_return_sorted = sorted(tool_return_ids)
            summary = f"{summary} tool_return_ids={tool_return_sorted}"
        logger.debug(summary)

        for part_index, part in enumerate(parts):
            part_summary = _format_part_debug(part, DEBUG_HISTORY_PART_PREVIEW_LEN)
            logger.debug(f"history[{msg_index}].part[{part_index}] {part_summary}")

        for tool_index, tool_call in enumerate(tool_calls):
            tool_summary = _format_tool_call_debug(tool_call, DEBUG_HISTORY_PART_PREVIEW_LEN)
            logger.debug(f"history[{msg_index}].tool_calls[{tool_index}] {tool_summary}")


def _filter_dangling_tool_calls_from_parts(
    parts: list[Any],
    dangling_tool_call_ids: set[ToolCallId],
) -> tuple[list[Any], bool]:
    """Remove dangling tool-call parts and return filtered parts."""
    if not parts:
        return parts, False

    filtered_parts: list[Any] = []
    removed_any = False

    for part in parts:
        part_kind = _get_attr_value(part, PART_KIND_ATTR)
        if part_kind != PART_KIND_TOOL_CALL:
            filtered_parts.append(part)
            continue

        tool_call_id = _get_attr_value(part, TOOL_CALL_ID_ATTR)
        if tool_call_id is None:
            filtered_parts.append(part)
            continue

        if tool_call_id in dangling_tool_call_ids:
            removed_any = True
            continue

        filtered_parts.append(part)

    return filtered_parts, removed_any


def _filter_dangling_tool_calls_from_tool_calls(
    tool_calls: list[Any],
    dangling_tool_call_ids: set[ToolCallId],
) -> tuple[list[Any], bool]:
    """Remove dangling entries from tool_calls lists."""
    if not tool_calls:
        return tool_calls, False

    filtered_tool_calls: list[Any] = []
    removed_any = False

    for tool_call in tool_calls:
        tool_call_id = _get_attr_value(tool_call, TOOL_CALL_ID_ATTR)
        if tool_call_id is None:
            filtered_tool_calls.append(tool_call)
            continue

        if tool_call_id in dangling_tool_call_ids:
            removed_any = True
            continue

        filtered_tool_calls.append(tool_call)

    return filtered_tool_calls, removed_any


def _strip_dangling_tool_calls_from_message(
    message: Any,
    dangling_tool_call_ids: set[ToolCallId],
) -> tuple[bool, bool]:
    """Remove dangling tool calls from a message and signal if it should be dropped."""
    parts = _get_message_parts(message)
    tool_calls = _get_message_tool_calls(message)

    filtered_parts, removed_from_parts = _filter_dangling_tool_calls_from_parts(
        parts,
        dangling_tool_call_ids,
    )
    filtered_tool_calls, removed_from_tool_calls = _filter_dangling_tool_calls_from_tool_calls(
        tool_calls,
        dangling_tool_call_ids,
    )

    if removed_from_parts:
        _set_message_parts(message, filtered_parts)
    if removed_from_tool_calls:
        _set_message_tool_calls(message, filtered_tool_calls)

    removed_any = removed_from_parts or removed_from_tool_calls
    should_drop = removed_any and not filtered_parts and not filtered_tool_calls
    return removed_any, should_drop


def _remove_dangling_tool_calls(
    messages: list[Any],
    tool_call_args_by_id: dict[ToolCallId, ToolArgs],
    dangling_tool_call_ids: set[ToolCallId] | None = None,
) -> bool:
    """Remove tool calls that never received tool returns and clear cached args."""
    if not messages:
        return False

    if dangling_tool_call_ids is None:
        dangling_tool_call_ids = _find_dangling_tool_call_ids(messages)
    if not dangling_tool_call_ids:
        return False

    removed_any = False
    remaining_messages: list[Any] = []

    for message in messages:
        removed_from_message, should_drop = _strip_dangling_tool_calls_from_message(
            message,
            dangling_tool_call_ids,
        )
        if removed_from_message:
            removed_any = True
        if should_drop:
            removed_any = True
            continue
        remaining_messages.append(message)

    if removed_any:
        messages[:] = remaining_messages
        for tool_call_id in dangling_tool_call_ids:
            tool_call_args_by_id.pop(tool_call_id, None)

    return removed_any


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
