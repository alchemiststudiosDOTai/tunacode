"""Module: tunacode.core.agents.main

Main agent functionality and coordination for the TunaCode CLI.
Handles agent creation, configuration, and request processing.

CLAUDE_ANCHOR[main-agent-module]: Primary agent orchestration and lifecycle management
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional

from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool  # noqa: F401

    from tunacode.core.agents.agent_components import ResponseState, ToolBuffer

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import ToolBatchingJSONError, UserAbortError
from tunacode.services.mcp import get_mcp_servers  # re-exported by design
from tunacode.tools.react import ReactTool
from tunacode.types import (
    AgentRun,
    ModelName,
    ToolCallback,
    UsageTrackerProtocol,
)

# CLAUDE_ANCHOR[key=d595ceb5] Direct UI console import aligns with removal of defensive shim
from tunacode.ui import console as ui
from tunacode.ui.tool_descriptions import get_batch_description

# Streaming parts (keep guarded import but avoid per-iteration imports)
try:
    from pydantic_ai.messages import PartDeltaEvent, TextPartDelta  # type: ignore

    STREAMING_AVAILABLE = True
except Exception:  # pragma: no cover
    PartDeltaEvent = None  # type: ignore
    TextPartDelta = None  # type: ignore
    STREAMING_AVAILABLE = False

from . import agent_components as ac

logger = get_logger(__name__)

__all__ = [
    "process_request",
    "get_mcp_servers",
    "get_agent_tool",
    "check_query_satisfaction",
]

DEFAULT_MAX_ITERATIONS = 15
UNPRODUCTIVE_LIMIT = 3  # iterations without tool use before forcing action
FALLBACK_VERBOSITY_DEFAULT = "normal"
DEBUG_METRICS_DEFAULT = False
FORCED_REACT_INTERVAL = 2
FORCED_REACT_LIMIT = 5


@dataclass(slots=True)
class RequestContext:
    request_id: str
    max_iterations: int
    debug_metrics: bool
    fallback_enabled: bool


class StateFacade:
    """wrapper to centralize session mutations and reads."""

    def __init__(self, state_manager: StateManager) -> None:
        self.sm = state_manager

    def get_setting(self, dotted: str, default: Any) -> Any:
        cfg: Dict[str, Any] = getattr(self.sm.session, "user_config", {}) or {}
        node = cfg
        for key in dotted.split("."):
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    @property
    def show_thoughts(self) -> bool:
        return bool(getattr(self.sm.session, "show_thoughts", False))

    @property
    def messages(self) -> list:
        return list(getattr(self.sm.session, "messages", []))

    def set_request_id(self, req_id: str) -> None:
        try:
            self.sm.session.request_id = req_id
        except AttributeError:
            logger.warning("Session missing 'request_id' attribute; unable to set (req=%s)", req_id)

    def reset_for_new_request(self) -> None:
        """Reset/initialize fields needed for a new run."""
        # Keep all assignments here to avoid scattered mutations across the codebase.
        setattr(self.sm.session, "current_iteration", 0)
        setattr(self.sm.session, "iteration_count", 0)
        setattr(self.sm.session, "tool_calls", [])
        setattr(self.sm.session, "react_forced_calls", 0)
        setattr(self.sm.session, "react_guidance", [])
        # Counter used by other subsystems; initialize if absent
        if not hasattr(self.sm.session, "batch_counter"):
            setattr(self.sm.session, "batch_counter", 0)
        # Track empty response streaks
        setattr(self.sm.session, "consecutive_empty_responses", 0)
        # Always reset original query so subsequent requests don't leak prompts
        setattr(self.sm.session, "original_query", "")

    def set_original_query_once(self, q: str) -> None:
        if not getattr(self.sm.session, "original_query", None):
            setattr(self.sm.session, "original_query", q)

    # ---- progress helpers ----
    def set_iteration(self, i: int) -> None:
        setattr(self.sm.session, "current_iteration", i)
        setattr(self.sm.session, "iteration_count", i)

    def increment_empty_response(self) -> int:
        v = int(getattr(self.sm.session, "consecutive_empty_responses", 0)) + 1
        setattr(self.sm.session, "consecutive_empty_responses", v)
        return v

    def clear_empty_response(self) -> None:
        setattr(self.sm.session, "consecutive_empty_responses", 0)


def _init_context(state: StateFacade, fallback_enabled: bool) -> RequestContext:
    req_id = str(uuid.uuid4())[:8]
    state.set_request_id(req_id)

    max_iters = int(state.get_setting("settings.max_iterations", DEFAULT_MAX_ITERATIONS))
    debug_metrics = bool(state.get_setting("settings.debug_metrics", DEBUG_METRICS_DEFAULT))

    return RequestContext(
        request_id=req_id,
        max_iterations=max_iters,
        debug_metrics=debug_metrics,
        fallback_enabled=fallback_enabled,
    )


def _prepare_message_history(state: StateFacade) -> list:
    return state.messages


async def _maybe_stream_node_tokens(
    node: Any,
    agent_run_ctx: Any,
    state_manager: StateManager,
    streaming_cb: Optional[Callable[[str], Awaitable[None]]],
    request_id: str,
    iteration_index: int,
) -> None:
    if not streaming_cb or not STREAMING_AVAILABLE:
        return

    # Delegate to component streaming helper (already optimized)
    if Agent.is_model_request_node(node):  # type: ignore[attr-defined]
        await ac.stream_model_request_node(
            node, agent_run_ctx, state_manager, streaming_cb, request_id, iteration_index
        )


def _iteration_had_tool_use(node: Any) -> bool:
    """Inspect the node to see if model responded with any tool-call parts."""
    if hasattr(node, "model_response"):
        for part in getattr(node.model_response, "parts", []):
            # pydantic-ai annotates tool calls; be resilient to attr differences
            if getattr(part, "part_kind", None) == "tool-call":
                return True
    return False


async def _maybe_force_react_snapshot(
    iteration: int,
    state_manager: StateManager,
    react_tool: ReactTool,
    show_debug: bool,
    agent_run_ctx: Any | None = None,
) -> None:
    """CLAUDE_ANCHOR[react-forced-call]: Auto-log reasoning every two turns."""

    if iteration < FORCED_REACT_INTERVAL or iteration % FORCED_REACT_INTERVAL != 0:
        return

    forced_calls = getattr(state_manager.session, "react_forced_calls", 0)
    if forced_calls >= FORCED_REACT_LIMIT:
        return

    try:
        await react_tool.execute(
            action="think",
            thoughts=f"Auto snapshot after iteration {iteration}",
            next_action="continue",
        )
        state_manager.session.react_forced_calls = forced_calls + 1
        timeline = state_manager.session.react_scratchpad.get("timeline", [])
        latest = timeline[-1] if timeline else {"thoughts": "?", "next_action": "?"}
        summary = latest.get("thoughts", "")
        tool_calls = getattr(state_manager.session, "tool_calls", [])
        if tool_calls:
            last_tool = tool_calls[-1]
            tool_name = last_tool.get("tool", "tool")
            args = last_tool.get("args", {})
            if isinstance(args, str):
                try:
                    import json

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
                path = args.get("filepath") or args.get("file_path")
                detail = f"Extract key notes from {path}" if path else "Summarize read_file output"
            else:
                detail = f"Act on {tool_name} findings"
        else:
            detail = "Plan your first lookup"
        guidance_entry = (
            f"React snapshot {forced_calls + 1}/{FORCED_REACT_LIMIT} at iteration {iteration}:"
            f" {summary}. Next: {detail}"
        )
        state_manager.session.react_guidance.append(guidance_entry)
        if len(state_manager.session.react_guidance) > FORCED_REACT_LIMIT:
            state_manager.session.react_guidance = state_manager.session.react_guidance[
                -FORCED_REACT_LIMIT:
            ]

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
                # This mutates the active run context so the very next model prompt includes the guidance
                ctx_messages.append(ModelRequest(parts=[system_part], kind="request"))

        if show_debug:
            await ui.muted("\n[react → LLM] BEGIN\n" + guidance_entry + "\n[react → LLM] END\n")
    except Exception:
        logger.debug("Forced react snapshot failed", exc_info=True)


async def _force_action_if_unproductive(
    message: str,
    unproductive_count: int,
    last_productive: int,
    i: int,
    max_iterations: int,
    state: StateFacade,
) -> None:
    no_progress_content = (
        f"ALERT: No tools executed for {unproductive_count} iterations.\n\n"
        f"Last productive iteration: {last_productive}\n"
        f"Current iteration: {i}/{max_iterations}\n"
        f"Task: {message[:200]}...\n\n"
        "You're describing actions but not executing them. You MUST:\n\n"
        "1. If task is COMPLETE: Start response with TUNACODE DONE:\n"
        "2. If task needs work: Execute a tool RIGHT NOW (grep, read_file, bash, etc.)\n"
        "3. If stuck: Explain the specific blocker\n\n"
        "NO MORE DESCRIPTIONS. Take ACTION or mark COMPLETE."
    )
    ac.create_user_message(no_progress_content, state.sm)
    if state.show_thoughts:
        await ui.warning(f"NO PROGRESS: {unproductive_count} iterations without tool usage")


async def _ask_for_clarification(i: int, state: StateFacade) -> None:
    _, tools_used_str = ac.create_progress_summary(getattr(state.sm.session, "tool_calls", []))

    clarification_content = (
        "I need clarification to continue.\n\n"
        f"Original request: {getattr(state.sm.session, 'original_query', 'your request')}\n\n"
        "Progress so far:\n"
        f"- Iterations: {i}\n"
        f"- Tools used: {tools_used_str}\n\n"
        "If the task is complete, I should respond with TUNACODE DONE:\n"
        "Otherwise, please provide specific guidance on what to do next."
    )

    ac.create_user_message(clarification_content, state.sm)
    if state.show_thoughts:
        await ui.muted("\nSEEKING CLARIFICATION: Asking user for guidance on task progress")


async def _finalize_buffered_tasks(
    tool_buffer: ToolBuffer,
    tool_callback: Optional[ToolCallback],
    state: StateFacade,
) -> None:
    if not tool_callback or not tool_buffer.has_tasks():
        return

    buffered_tasks = tool_buffer.flush()

    # Cosmetic UI around batch (kept but isolated here)
    try:
        tool_names = [part.tool_name for part, _ in buffered_tasks]
        batch_msg = get_batch_description(len(buffered_tasks), tool_names)
        await ui.update_spinner_message(f"[bold #00d7ff]{batch_msg}...[/bold #00d7ff]", state.sm)
        await ui.muted("\n" + "=" * 60)
        await ui.muted(f"FINAL BATCH: Executing {len(buffered_tasks)} buffered read-only tools")
        await ui.muted("=" * 60)
        for idx, (part, _node) in enumerate(buffered_tasks, 1):
            tool_desc = f"  [{idx}] {getattr(part, 'tool_name', 'tool')}"
            args = getattr(part, "args", {})
            if isinstance(args, dict):
                if part.tool_name == "read_file" and "file_path" in args:
                    tool_desc += f" → {args['file_path']}"
                elif part.tool_name == "grep" and "pattern" in args:
                    tool_desc += f" → pattern: '{args['pattern']}'"
                    if "include_files" in args:
                        tool_desc += f", files: '{args['include_files']}'"
                elif part.tool_name == "list_dir" and "directory" in args:
                    tool_desc += f" → {args['directory']}"
                elif part.tool_name == "glob" and "pattern" in args:
                    tool_desc += f" → pattern: '{args['pattern']}'"
            await ui.muted(tool_desc)
        await ui.muted("=" * 60)
    except Exception:
        # UI is best-effort; never fail request because of display
        logger.debug("UI batch prelude failed (non-fatal)", exc_info=True)

    # Execute
    start = time.time()
    await ac.execute_tools_parallel(buffered_tasks, tool_callback)
    elapsed_ms = (time.time() - start) * 1000

    # Post metrics (best-effort)
    try:
        sequential_estimate = len(buffered_tasks) * 100.0
        speedup = (sequential_estimate / elapsed_ms) if elapsed_ms > 0 else 1.0
        await ui.muted(
            f"Final batch completed in {elapsed_ms:.0f}ms (~{speedup:.1f}x faster than sequential)\n"
        )
        from tunacode.constants import UI_THINKING_MESSAGE  # local import OK (rare path)

        await ui.update_spinner_message(UI_THINKING_MESSAGE, state.sm)
    except Exception:
        logger.debug("UI batch epilogue failed (non-fatal)", exc_info=True)


def _should_build_fallback(
    response_state: ResponseState,
    iter_idx: int,
    max_iterations: int,
    fallback_enabled: bool,
) -> bool:
    return (
        fallback_enabled
        and not response_state.has_user_response
        and not response_state.task_completed
        and iter_idx >= max_iterations
    )


def _build_fallback_output(
    iter_idx: int,
    max_iterations: int,
    state: StateFacade,
) -> str:
    verbosity = state.get_setting("settings.fallback_verbosity", FALLBACK_VERBOSITY_DEFAULT)
    fallback = ac.create_fallback_response(
        iter_idx,
        max_iterations,
        getattr(state.sm.session, "tool_calls", []),
        getattr(state.sm.session, "messages", []),
        verbosity,
    )
    return ac.format_fallback_output(fallback)


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
    usage_tracker: Optional[
        UsageTrackerProtocol
    ] = None,  # currently passed through to _process_node
    fallback_enabled: bool = True,
) -> AgentRun:
    """
    Process a single request to the agent.

    CLAUDE_ANCHOR[process-request-entry]: Main entry point for all agent requests
    """
    state = StateFacade(state_manager)
    fallback_config_enabled = bool(state.get_setting("settings.fallback_response", True))
    ctx = _init_context(state, fallback_enabled=fallback_enabled and fallback_config_enabled)
    state.reset_for_new_request()
    state.set_original_query_once(message)

    # Acquire agent (no local caching here; rely on upstream policies)
    agent = ac.get_or_create_agent(model, state_manager)

    # Prepare history snapshot
    message_history = _prepare_message_history(state)

    # Per-request trackers
    tool_buffer = ac.ToolBuffer()
    response_state = ac.ResponseState()
    unproductive_iterations = 0
    last_productive_iteration = 0
    react_tool = ReactTool(state_manager=state_manager)

    try:
        async with agent.iter(message, message_history=message_history) as agent_run:
            i = 1
            async for node in agent_run:
                state.set_iteration(i)

                # Optional token streaming
                await _maybe_stream_node_tokens(
                    node, agent_run.ctx, state_manager, streaming_callback, ctx.request_id, i
                )

                # Core node processing (delegated to components)
                empty_response, empty_reason = await ac._process_node(  # noqa: SLF001 (private but stable in repo)
                    node,
                    tool_callback,
                    state_manager,
                    tool_buffer,
                    streaming_callback,
                    usage_tracker,
                    response_state,
                )

                # Handle empty response (aggressive retry prompt)
                if empty_response:
                    if state.increment_empty_response() >= 1:
                        await ac.handle_empty_response(message, empty_reason, i, state)
                        state.clear_empty_response()
                else:
                    state.clear_empty_response()

                # Track whether we produced visible user output this iteration
                if getattr(getattr(node, "result", None), "output", None):
                    response_state.has_user_response = True

                # Productivity tracking (tool usage signal)
                if _iteration_had_tool_use(node):
                    unproductive_iterations = 0
                    last_productive_iteration = i
                else:
                    unproductive_iterations += 1

                # Force action if no tool usage for several iterations
                if (
                    unproductive_iterations >= UNPRODUCTIVE_LIMIT
                    and not response_state.task_completed
                ):
                    await _force_action_if_unproductive(
                        message,
                        unproductive_iterations,
                        last_productive_iteration,
                        i,
                        ctx.max_iterations,
                        state,
                    )
                    unproductive_iterations = 0  # reset after nudge

                await _maybe_force_react_snapshot(
                    i,
                    state_manager,
                    react_tool,
                    state.show_thoughts,
                    agent_run.ctx,
                )

                # Optional debug progress
                if state.show_thoughts:
                    await ui.muted(
                        f"\nITERATION: {i}/{ctx.max_iterations} (Request ID: {ctx.request_id})"
                    )
                    tool_summary = ac.get_tool_summary(getattr(state.sm.session, "tool_calls", []))
                    if tool_summary:
                        summary_str = ", ".join(
                            f"{name}: {count}" for name, count in tool_summary.items()
                        )
                        await ui.muted(f"TOOLS USED: {summary_str}")

                # Ask for clarification if agent requested it
                if response_state.awaiting_user_guidance:
                    await _ask_for_clarification(i, state)
                    # Keep the flag set; downstream logic can react to new user input

                # Early completion
                if response_state.task_completed:
                    if state.show_thoughts:
                        await ui.success("Task completed successfully")
                    break

                # Reaching iteration cap → ask what to do next (no auto-extend by default)
                if i >= ctx.max_iterations and not response_state.task_completed:
                    _, tools_str = ac.create_progress_summary(
                        getattr(state.sm.session, "tool_calls", [])
                    )
                    if tools_str == "No tools used yet":
                        tools_str = "No tools used"

                    extend_content = (
                        f"I've reached the iteration limit ({ctx.max_iterations}).\n\n"
                        "Progress summary:\n"
                        f"- Tools used: {tools_str}\n"
                        f"- Iterations completed: {i}\n\n"
                        "Plese add more context to the task."
                    )
                    ac.create_user_message(extend_content, state.sm)
                    if state.show_thoughts:
                        await ui.muted(
                            f"\nITERATION LIMIT: Awaiting user guidance at {ctx.max_iterations} iterations"
                        )
                    response_state.awaiting_user_guidance = True
                    # Do not auto-increase max_iterations here (avoid infinite loops)

                i += 1

            await _finalize_buffered_tasks(tool_buffer, tool_callback, state)

            # Build fallback synthesis if needed
            if _should_build_fallback(response_state, i, ctx.max_iterations, ctx.fallback_enabled):
                ac.patch_tool_messages("Task incomplete", state_manager=state_manager)
                response_state.has_final_synthesis = True
                comprehensive_output = _build_fallback_output(i, ctx.max_iterations, state)
                wrapper = ac.AgentRunWrapper(
                    agent_run, ac.SimpleResult(comprehensive_output), response_state
                )
                return wrapper

            # Normal path: return a wrapper that carries response_state
            return ac.AgentRunWithState(agent_run, response_state)

    except UserAbortError:
        raise
    except ToolBatchingJSONError as e:
        logger.error("Tool batching JSON error [req=%s]: %s", ctx.request_id, e, exc_info=True)
        ac.patch_tool_messages(
            f"Tool batching failed: {str(e)[:100]}...", state_manager=state_manager
        )
        raise
    except Exception as e:
        # Attach request/iteration context for observability
        safe_iter = getattr(state_manager.session, "current_iteration", "?")
        logger.error(
            "Error in process_request [req=%s iter=%s]: %s",
            ctx.request_id,
            safe_iter,
            e,
            exc_info=True,
        )
        ac.patch_tool_messages(
            f"Request processing failed: {str(e)[:100]}...", state_manager=state_manager
        )
        raise
