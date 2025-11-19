"""Module: tunacode.core.agents.main

Refactored main agent functionality with focused responsibility classes.
Handles agent creation, configuration, and request processing.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool  # noqa: F401

from tunacode.constants import UI_COLORS
from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import ToolBatchingJSONError, UserAbortError
from tunacode.services.mcp import (  # re-exported by design
    cleanup_mcp_servers,
    get_mcp_servers,
    register_mcp_agent,
)
from tunacode.tools.react import ReactTool
from tunacode.types import (
    AgentRun,
    ModelName,
    ToolCallback,
    UsageTrackerProtocol,
)
from tunacode.ui import console as ui
from tunacode.ui.tool_descriptions import get_batch_description
from tunacode.utils.file_utils import DotDict

from . import agent_components as ac
from .prompts import format_clarification, format_iteration_limit, format_no_progress

logger = get_logger(__name__)
colors = DotDict(UI_COLORS)

__all__ = [
    "process_request",
    "get_mcp_servers",
    "cleanup_mcp_servers",
    "register_mcp_agent",
    "get_agent_tool",
    "check_query_satisfaction",
]


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""

    max_iterations: int = 15
    unproductive_limit: int = 3
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

    def __init__(self, state_manager: StateManager) -> None:
        self.state_manager = state_manager

    def track(self, is_empty: bool) -> None:
        """Track empty response and increment counter if empty."""
        if is_empty:
            current = getattr(self.state_manager.session, "consecutive_empty_responses", 0)
            setattr(self.state_manager.session, "consecutive_empty_responses", current + 1)
        else:
            setattr(self.state_manager.session, "consecutive_empty_responses", 0)

    def should_intervene(self) -> bool:
        """Check if intervention is needed (>= 1 consecutive empty)."""
        return getattr(self.state_manager.session, "consecutive_empty_responses", 0) >= 1

    async def prompt_action(self, message: str, reason: str, iteration: int) -> None:
        """Delegate to agent_components.handle_empty_response."""

        # Create a minimal state-like object for compatibility
        class StateProxy:
            def __init__(self, sm: StateManager) -> None:
                self.sm = sm
                self.show_thoughts = bool(getattr(sm.session, "show_thoughts", False))

        state_proxy = StateProxy(self.state_manager)
        await ac.handle_empty_response(message, reason, iteration, state_proxy)
        # Clear after intervention
        setattr(self.state_manager.session, "consecutive_empty_responses", 0)


class IterationManager:
    """Manages iteration tracking, productivity monitoring, and limit handling."""

    def __init__(self, state_manager: StateManager, config: AgentConfig) -> None:
        self.state_manager = state_manager
        self.config = config
        self.unproductive_iterations = 0
        self.last_productive_iteration = 0

    def track_productivity(self, had_tool_use: bool, iteration: int) -> None:
        """Track productivity based on tool usage."""
        if had_tool_use:
            self.unproductive_iterations = 0
            self.last_productive_iteration = iteration
        else:
            self.unproductive_iterations += 1

    def should_force_action(self, response_state: ac.ResponseState) -> bool:
        """Check if action should be forced due to unproductivity."""
        return (
            self.unproductive_iterations >= self.config.unproductive_limit
            and not response_state.task_completed
        )

    async def handle_iteration_limit(
        self, iteration: int, response_state: ac.ResponseState
    ) -> None:
        """Handle reaching iteration limit."""
        if iteration >= self.config.max_iterations and not response_state.task_completed:
            _, tools_str = ac.create_progress_summary(
                getattr(self.state_manager.session, "tool_calls", [])
            )
            limit_message = format_iteration_limit(self.config.max_iterations, iteration, tools_str)
            ac.create_user_message(limit_message, self.state_manager)

            if getattr(self.state_manager.session, "show_thoughts", False):
                await ui.muted(
                    f"\nITERATION LIMIT: Awaiting user guidance at "
                    f"{self.config.max_iterations} iterations"
                )

            response_state.awaiting_user_guidance = True

    def update_counters(self, iteration: int) -> None:
        """Update session iteration counters."""
        self.state_manager.session.current_iteration = iteration
        self.state_manager.session.iteration_count = iteration

    async def force_action_if_unproductive(
        self, message: str, iteration: int, response_state: ac.ResponseState
    ) -> None:
        """Force action if unproductive iterations exceeded."""
        if not self.should_force_action(response_state):
            return

        no_progress_message = format_no_progress(
            message,
            self.unproductive_iterations,
            self.last_productive_iteration,
            iteration,
            self.config.max_iterations,
        )
        ac.create_user_message(no_progress_message, self.state_manager)

        if getattr(self.state_manager.session, "show_thoughts", False):
            await ui.warning(
                f"NO PROGRESS: {self.unproductive_iterations} iterations without tool usage"
            )

        # Reset after nudge
        self.unproductive_iterations = 0

    async def ask_for_clarification(self, iteration: int) -> None:
        """Ask user for clarification."""
        _, tools_used_str = ac.create_progress_summary(
            getattr(self.state_manager.session, "tool_calls", [])
        )
        original_query = getattr(self.state_manager.session, "original_query", "your request")
        clarification_message = format_clarification(original_query, iteration, tools_used_str)
        ac.create_user_message(clarification_message, self.state_manager)

        if getattr(self.state_manager.session, "show_thoughts", False):
            await ui.muted("\nSEEKING CLARIFICATION: Asking user for guidance on task progress")


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

    async def capture_snapshot(self, iteration: int, agent_run_ctx: Any, show_debug: bool) -> None:
        """Capture react snapshot and inject guidance."""
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
                if isinstance(ctx_messages, list):
                    ModelRequest, _, SystemPromptPart = ac.get_model_messages()
                    system_part = SystemPromptPart(
                        content=f"[React Guidance] {guidance_entry}",
                        part_kind="system-prompt",
                    )
                    # CLAUDE_ANCHOR[react-system-injection]
                    # Append synthetic system message so LLM receives react guidance next turn
                    ctx_messages.append(ModelRequest(parts=[system_part], kind="request"))

            if show_debug:
                await ui.muted("\n[react → LLM] BEGIN\n" + guidance_entry + "\n[react → LLM] END\n")
        except Exception:
            logger.debug("Forced react snapshot failed", exc_info=True)


class RequestOrchestrator:
    """Orchestrates the main request processing loop."""

    def __init__(
        self,
        message: str,
        model: ModelName,
        state_manager: StateManager,
        tool_callback: Optional[ToolCallback],
        streaming_callback: Optional[Callable[[str], Awaitable[None]]],
        usage_tracker: Optional[UsageTrackerProtocol],
    ) -> None:
        self.message = message
        self.model = model
        self.state_manager = state_manager
        self.tool_callback = tool_callback
        self.streaming_callback = streaming_callback
        self.usage_tracker = usage_tracker

        # Initialize config from session settings
        user_config = getattr(state_manager.session, "user_config", {}) or {}
        settings = user_config.get("settings", {})
        self.config = AgentConfig(
            max_iterations=int(settings.get("max_iterations", 15)),
            unproductive_limit=3,
            forced_react_interval=2,
            forced_react_limit=5,
            debug_metrics=bool(settings.get("debug_metrics", False)),
        )

        # Initialize managers
        self.empty_handler = EmptyResponseHandler(state_manager)
        self.iteration_manager = IterationManager(state_manager, self.config)
        self.react_manager = ReactSnapshotManager(
            state_manager, ReactTool(state_manager=state_manager), self.config
        )

    def _init_request_context(self) -> RequestContext:
        """Initialize request context with ID and config."""
        req_id = str(uuid.uuid4())[:8]
        setattr(self.state_manager.session, "request_id", req_id)

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
        self.state_manager.session.react_forced_calls = 0
        self.state_manager.session.react_guidance = []

        # Counter used by other subsystems; initialize if absent
        if not hasattr(self.state_manager.session, "batch_counter"):
            self.state_manager.session.batch_counter = 0

        # Track empty response streaks
        setattr(self.state_manager.session, "consecutive_empty_responses", 0)

        setattr(self.state_manager.session, "original_query", "")

    def _set_original_query_once(self, query: str) -> None:
        """Set original query if not already set."""
        if not getattr(self.state_manager.session, "original_query", None):
            setattr(self.state_manager.session, "original_query", query)

    async def run(self) -> AgentRun:
        """Run the main request processing loop."""
        ctx = self._init_request_context()
        self._reset_session_state()
        self._set_original_query_once(self.message)

        # Acquire agent
        agent = ac.get_or_create_agent(self.model, self.state_manager)

        # Prepare history snapshot
        message_history = list(getattr(self.state_manager.session, "messages", []))

        # Per-request trackers
        tool_buffer = ac.ToolBuffer()
        response_state = ac.ResponseState()

        try:
            async with agent.iter(self.message, message_history=message_history) as agent_run:
                i = 1
                async for node in agent_run:
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
                    empty_response, empty_reason = await ac._process_node(  # noqa: SLF001
                        node,
                        self.tool_callback,
                        self.state_manager,
                        tool_buffer,
                        self.streaming_callback,
                        self.usage_tracker,
                        response_state,
                    )

                    # Handle empty response
                    self.empty_handler.track(empty_response)
                    if empty_response and self.empty_handler.should_intervene():
                        await self.empty_handler.prompt_action(self.message, empty_reason, i)

                    # Track whether we produced visible user output this iteration
                    if getattr(getattr(node, "result", None), "output", None):
                        response_state.has_user_response = True

                    # Productivity tracking
                    had_tool_use = _iteration_had_tool_use(node)
                    self.iteration_manager.track_productivity(had_tool_use, i)

                    # Force action if unproductive
                    await self.iteration_manager.force_action_if_unproductive(
                        self.message, i, response_state
                    )

                    # Force react snapshot
                    show_thoughts = bool(
                        getattr(self.state_manager.session, "show_thoughts", False)
                    )
                    await self.react_manager.capture_snapshot(i, agent_run.ctx, show_thoughts)

                    # Optional debug progress
                    if show_thoughts:
                        await ui.muted(
                            f"\nITERATION: {i}/{ctx.max_iterations} (Request ID: {ctx.request_id})"
                        )
                        tool_summary = ac.get_tool_summary(
                            getattr(self.state_manager.session, "tool_calls", [])
                        )
                        if tool_summary:
                            summary_str = ", ".join(
                                f"{name}: {count}" for name, count in tool_summary.items()
                            )
                            await ui.muted(f"TOOLS USED: {summary_str}")

                    # Ask for clarification if agent requested it
                    if response_state.awaiting_user_guidance:
                        await self.iteration_manager.ask_for_clarification(i)

                    # Early completion
                    if response_state.task_completed:
                        if show_thoughts:
                            await ui.success("Task completed successfully")
                        break

                    # Handle iteration limit
                    await self.iteration_manager.handle_iteration_limit(i, response_state)

                    i += 1

                await _finalize_buffered_tasks(tool_buffer, self.tool_callback, self.state_manager)

                # Return wrapper that carries response_state
                return ac.AgentRunWithState(agent_run, response_state)

        except UserAbortError:
            # User aborts must propagate - they represent user intent
            raise
        except ToolBatchingJSONError as e:
            # Log error and patch messages, but return gracefully instead of raising
            logger.error("Tool batching JSON error [req=%s]: %s", ctx.request_id, e, exc_info=True)
            error_msg = f"Tool batching failed: {str(e)[:100]}..."
            ac.patch_tool_messages(error_msg, state_manager=self.state_manager)
            # Return wrapper with fallback result - agent_run context has exited
            fallback = ac.SimpleResult(error_msg)
            return ac.AgentRunWrapper(None, fallback, response_state)
        except Exception as e:
            # Attach request/iteration context for observability
            safe_iter = getattr(self.state_manager.session, "current_iteration", "?")
            logger.error(
                "Error in process_request [req=%s iter=%s]: %s",
                ctx.request_id,
                safe_iter,
                e,
                exc_info=True,
            )
            error_msg = f"Request processing failed: {str(e)[:100]}..."
            ac.patch_tool_messages(error_msg, state_manager=self.state_manager)
            # Return wrapper with fallback result - agent_run context has exited
            fallback = ac.SimpleResult(error_msg)
            return ac.AgentRunWrapper(None, fallback, response_state)


# Utility functions


async def _maybe_stream_node_tokens(
    node: Any,
    agent_run_ctx: Any,
    state_manager: StateManager,
    streaming_cb: Optional[Callable[[str], Awaitable[None]]],
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
        await ac.stream_model_request_node(
            node, agent_run_ctx, state_manager, streaming_cb, request_id, iteration_index
        )


def _iteration_had_tool_use(node: Any) -> bool:
    """Inspect the node to see if model responded with any tool-call parts.

    Reference: main.py lines 164-171
    """
    if hasattr(node, "model_response"):
        for part in getattr(node.model_response, "parts", []):
            # pydantic-ai annotates tool calls; be resilient to attr differences
            if getattr(part, "part_kind", None) == "tool-call":
                return True
    return False


async def _finalize_buffered_tasks(
    tool_buffer: ac.ToolBuffer,
    tool_callback: Optional[ToolCallback],
    state_manager: StateManager,
) -> None:
    """Finalize and execute any buffered read-only tasks."""
    if not tool_callback or not tool_buffer.has_tasks():
        return

    buffered_tasks = tool_buffer.flush()

    # Update spinner message (best-effort)
    try:
        tool_names = [part.tool_name for part, _ in buffered_tasks]
        batch_msg = get_batch_description(len(buffered_tasks), tool_names)
        await ui.update_spinner_message(
            f"[bold {colors.primary}]{batch_msg}...[/bold {colors.primary}]", state_manager
        )
    except Exception:
        # UI is best-effort; never fail request because of display
        logger.debug("UI batch prelude failed (non-fatal)", exc_info=True)

    # Execute
    await ac.execute_tools_parallel(buffered_tasks, tool_callback)

    # Reset spinner message (best-effort)
    try:
        from tunacode.constants import UI_THINKING_MESSAGE  # local import OK (rare path)

        await ui.update_spinner_message(UI_THINKING_MESSAGE, state_manager)
    except Exception:
        logger.debug("UI batch epilogue failed (non-fatal)", exc_info=True)


def get_agent_tool() -> tuple[type[Agent], type["Tool"]]:
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
    tool_callback: Optional[ToolCallback] = None,
    streaming_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    usage_tracker: Optional[UsageTrackerProtocol] = None,
) -> AgentRun:

    orchestrator = RequestOrchestrator(
        message,
        model,
        state_manager,
        tool_callback,
        streaming_callback,
        usage_tracker,
    )
    return await orchestrator.run()
