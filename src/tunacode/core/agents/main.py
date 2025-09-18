"""Module: tunacode.core.agents.main

Main agent functionality and coordination for the TunaCode CLI.
Handles agent creation, configuration, and request processing.

CLAUDE_ANCHOR[main-agent-module]: Primary agent orchestration and lifecycle management
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool  # noqa: F401

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import ToolBatchingJSONError, UserAbortError
from tunacode.services.mcp import get_mcp_servers  # re-exported by design
from tunacode.types import (
    AgentRun,
    ModelName,
    ToolCallback,
    UsageTrackerProtocol,
)

# Optional UI console (avoid nested imports in hot paths)
try:
    from tunacode.ui import console as ui  # rich-style helpers with async methods
except Exception:  # pragma: no cover - UI is optional

    class _NoopUI:  # minimal no-op shim
        async def muted(self, *_: Any, **__: Any) -> None: ...
        async def warning(self, *_: Any, **__: Any) -> None: ...
        async def success(self, *_: Any, **__: Any) -> None: ...
        async def update_spinner_message(self, *_: Any, **__: Any) -> None: ...

    ui = _NoopUI()  # type: ignore

# Streaming parts (keep guarded import but avoid per-iteration imports)
try:
    from pydantic_ai.messages import PartDeltaEvent, TextPartDelta  # type: ignore

    STREAMING_AVAILABLE = True
except Exception:  # pragma: no cover
    PartDeltaEvent = None  # type: ignore
    TextPartDelta = None  # type: ignore
    STREAMING_AVAILABLE = False

# Agent components (collapse to a single module import to reduce coupling)
from . import agent_components as ac  # noqa: E402
from .react_pattern import ReactCoordinator
from .state_facade import StateFacade

# Configure logging
logger = get_logger(__name__)

# -----------------------
# Backwards-compatible exports (rely on agent_components)
# -----------------------
ToolBuffer = ac.ToolBuffer
ResponseState = ac.ResponseState
AgentRunWrapper = ac.AgentRunWrapper
AgentRunWithState = ac.AgentRunWithState
SimpleResult = ac.SimpleResult
check_task_completion = ac.check_task_completion
extract_and_execute_tool_calls = ac.extract_and_execute_tool_calls
parse_json_tool_calls = ac.parse_json_tool_calls
get_model_messages = ac.get_model_messages
patch_tool_messages = ac.patch_tool_messages
get_or_create_agent = ac.get_or_create_agent
get_react_agents = ac.get_react_agents
_process_node = ac._process_node  # noqa: SLF001 - intentionally re-exported for compatibility
execute_tools_parallel = ac.execute_tools_parallel
create_empty_response_message = ac.create_empty_response_message
create_fallback_response = ac.create_fallback_response
create_progress_summary = ac.create_progress_summary
create_user_message = ac.create_user_message
format_fallback_output = ac.format_fallback_output
get_recent_tools_context = ac.get_recent_tools_context
get_tool_summary = ac.get_tool_summary
get_batch_description = ac.get_batch_description
flush_buffered_read_only_tools = ac.flush_buffered_read_only_tools
ToolFlushCoordinator = ac.ToolFlushCoordinator

# -----------------------
# Module exports
# -----------------------
__all__ = [
    "process_request",
    "get_mcp_servers",
    "ToolBuffer",
    "check_task_completion",
    "extract_and_execute_tool_calls",
    "parse_json_tool_calls",
    "get_model_messages",
    "patch_tool_messages",
    "get_or_create_agent",
    "get_react_agents",
    "_process_node",
    "ResponseState",
    "SimpleResult",
    "AgentRunWrapper",
    "AgentRunWithState",
    "execute_tools_parallel",
    "create_empty_response_message",
    "create_fallback_response",
    "create_progress_summary",
    "create_user_message",
    "format_fallback_output",
    "get_recent_tools_context",
    "get_tool_summary",
    "get_agent_tool",
    "check_query_satisfaction",
    "flush_buffered_read_only_tools",
    "ToolFlushCoordinator",
]

# -----------------------
# Constants & Defaults
# -----------------------
DEFAULT_MAX_ITERATIONS = 15  # replaces magic numbers
UNPRODUCTIVE_LIMIT = 3  # iterations without tool use before forcing action
REACT_MAX_STEPS = 4  # maximum number of planner/evaluator cycles per request
FALLBACK_VERBOSITY_DEFAULT = "normal"
DEBUG_METRICS_DEFAULT = False


# -----------------------
# Data structures
# -----------------------
@dataclass(slots=True)
class RequestContext:
    request_id: str
    max_iterations: int
    debug_metrics: bool
    fallback_enabled: bool


# -----------------------
# Helper functions
# -----------------------
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


def _node_output_text(node: Any) -> str:
    result = getattr(node, "result", None)
    if result is None:
        return ""
    output = getattr(result, "output", None)
    if isinstance(output, str):
        return output
    if output is None:
        return ""
    return str(output)


async def _maybe_stream_node_tokens(
    node: Any,
    agent_run_ctx: Any,
    state_manager: StateManager,
    streaming_cb: Optional[Callable[[str], Awaitable[None]]],
    request_id: str,
    iteration_index: int,
    tool_buffer: Optional[ToolBuffer] = None,
    tool_callback: Optional[ToolCallback] = None,
    flush_coordinator: Optional[ToolFlushCoordinator] = None,
) -> None:
    is_model_request = False
    try:
        is_model_request = Agent.is_model_request_node(node)  # type: ignore[attr-defined]
    except Exception:
        is_model_request = False

    if is_model_request and (not streaming_cb or not STREAMING_AVAILABLE):
        if flush_coordinator is not None:
            await flush_coordinator.ensure_before_request("pre-request:non-streaming")

    if not streaming_cb or not STREAMING_AVAILABLE:
        return

    # Delegate to component streaming helper (already optimized)
    if is_model_request:
        await ac.stream_model_request_node(
            node,
            agent_run_ctx,
            state_manager,
            streaming_cb,
            request_id,
            iteration_index,
            tool_buffer,
            tool_callback,
            flush_coordinator,
        )


def _iteration_had_tool_use(node: Any) -> bool:
    """Inspect the node to see if model responded with any tool-call parts."""
    if hasattr(node, "model_response"):
        for part in getattr(node.model_response, "parts", []):
            # pydantic-ai annotates tool calls; be resilient to attr differences
            if getattr(part, "part_kind", None) == "tool-call":
                return True
    return False


async def _handle_empty_response(
    message: str,
    reason: str,
    iter_index: int,
    state: StateFacade,
) -> None:
    force_action_content = create_empty_response_message(
        message,
        reason,
        getattr(state.sm.session, "tool_calls", []),
        iter_index,
        state.sm,
    )
    create_user_message(force_action_content, state.sm)

    if state.show_thoughts:
        await ui.warning("\nEMPTY RESPONSE FAILURE - AGGRESSIVE RETRY TRIGGERED")
        await ui.muted(f"   Reason: {reason}")
        await ui.muted(
            f"   Recent tools: {get_recent_tools_context(getattr(state.sm.session, 'tool_calls', []))}"
        )
        await ui.muted("   Injecting retry guidance prompt")


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
    create_user_message(no_progress_content, state.sm)
    if state.show_thoughts:
        await ui.warning(f"NO PROGRESS: {unproductive_count} iterations without tool usage")


async def _ask_for_clarification(i: int, state: StateFacade) -> None:
    _, tools_used_str = create_progress_summary(getattr(state.sm.session, "tool_calls", []))

    clarification_content = (
        "I need clarification to continue.\n\n"
        f"Original request: {getattr(state.sm.session, 'original_query', 'your request')}\n\n"
        "Progress so far:\n"
        f"- Iterations: {i}\n"
        f"- Tools used: {tools_used_str}\n\n"
        "If the task is complete, I should respond with TUNACODE DONE:\n"
        "Otherwise, please provide specific guidance on what to do next."
    )

    create_user_message(clarification_content, state.sm)
    if state.show_thoughts:
        await ui.muted("\nSEEKING CLARIFICATION: Asking user for guidance on task progress")


async def _finalize_buffered_tasks(
    flush_coordinator: ToolFlushCoordinator,
    state: StateFacade,
) -> None:
    executed = await flush_coordinator.flush(
        origin="final-batch",
        detailed=True,
        banner="FINAL BATCH",
    )

    if executed:
        try:
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
    fallback = create_fallback_response(
        iter_idx,
        max_iterations,
        getattr(state.sm.session, "tool_calls", []),
        getattr(state.sm.session, "messages", []),
        verbosity,
    )
    return format_fallback_output(fallback)


# -----------------------
# Public API
# -----------------------
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

    react_coordinator: Optional[ReactCoordinator] = None
    react_enabled = bool(state.get_setting("settings.enable_react", False))
    # TEMPORARY: Disable REACT to test file tagging without REACT interference unless explicitly enabled
    if react_enabled and not state_manager.is_plan_mode():
        try:
            planner_agent, evaluator_agent = get_react_agents(model, state_manager)
            react_coordinator = ReactCoordinator(
                planner_agent,
                evaluator_agent,
                state,
                max_steps=min(REACT_MAX_STEPS, ctx.max_iterations),
                ui_helper=ui,
            )
            await react_coordinator.bootstrap(message)
        except Exception as e:
            logger.warning(f"ReAct loop initialization failed: {e}", exc_info=True)
            react_coordinator = None

    # Acquire agent (no local caching here; rely on upstream policies)
    agent = get_or_create_agent(model, state_manager)

    # Prepare history snapshot
    message_history = _prepare_message_history(state)

    # Per-request trackers
    tool_buffer = ToolBuffer()
    # CLAUDE_ANCHOR[tool-flush-coordinator-8f1d0e2a]: Serializes buffered tool execution + validation
    flush_coordinator = ToolFlushCoordinator(state_manager, tool_buffer, tool_callback)
    response_state = ResponseState()
    unproductive_iterations = 0
    last_productive_iteration = 0

    try:
        async with agent.iter(message, message_history=message_history) as agent_run:
            i = 1
            async for node in agent_run:
                state.set_iteration(i)

                # Optional token streaming
                await _maybe_stream_node_tokens(
                    node,
                    agent_run.ctx,
                    state_manager,
                    streaming_callback,
                    ctx.request_id,
                    i,
                    tool_buffer,
                    tool_callback,
                    flush_coordinator,
                )

                # Core node processing (delegated to components)
                empty_response, empty_reason = await _process_node(  # noqa: SLF001 (private but stable in repo)
                    node,
                    tool_callback,
                    state_manager,
                    tool_buffer,
                    streaming_callback,
                    usage_tracker,
                    response_state,
                    flush_coordinator,
                )

                # Handle empty response (aggressive retry prompt)
                if empty_response:
                    await flush_coordinator.flush(origin="empty-response")
                    if state.increment_empty_response() >= 1:
                        await _handle_empty_response(message, empty_reason, i, state)
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
                    await flush_coordinator.flush(origin="unproductive-retry")
                    await _force_action_if_unproductive(
                        message,
                        unproductive_iterations,
                        last_productive_iteration,
                        i,
                        ctx.max_iterations,
                        state,
                    )
                    unproductive_iterations = 0  # reset after nudge

                # Optional debug progress
                if state.show_thoughts:
                    await ui.muted(
                        f"\nITERATION: {i}/{ctx.max_iterations} (Request ID: {ctx.request_id})"
                    )
                    tool_summary = get_tool_summary(getattr(state.sm.session, "tool_calls", []))
                    if tool_summary:
                        summary_str = ", ".join(
                            f"{name}: {count}" for name, count in tool_summary.items()
                        )
                        await ui.muted(f"TOOLS USED: {summary_str}")

                # Ask for clarification if agent requested it
                if response_state.awaiting_user_guidance:
                    await _ask_for_clarification(i, state)
                    # Keep the flag set; downstream logic can react to new user input

                if react_coordinator and not response_state.task_completed:
                    observation_text = _node_output_text(node)
                    can_continue = (
                        not response_state.awaiting_user_guidance and i < ctx.max_iterations
                    )
                    await react_coordinator.observe_step(
                        message,
                        observation_text,
                        can_continue=can_continue,
                    )

                # Early completion
                if response_state.task_completed:
                    if state.show_thoughts:
                        await ui.success("Task completed successfully")
                    break

                # Reaching iteration cap → ask what to do next (no auto-extend by default)
                if i >= ctx.max_iterations and not response_state.task_completed:
                    await flush_coordinator.flush(origin="iteration-cap")
                    _, tools_str = create_progress_summary(
                        getattr(state.sm.session, "tool_calls", [])
                    )
                    if tools_str == "No tools used yet":
                        tools_str = "No tools used"

                    extend_content = (
                        f"I've reached the iteration limit ({ctx.max_iterations}).\n\n"
                        "Progress summary:\n"
                        f"- Tools used: {tools_str}\n"
                        f"- Iterations completed: {i}\n\n"
                        "The task appears incomplete. Would you like me to:\n"
                        "1. Continue working (extend limit)\n"
                        "2. Summarize what I've done and stop\n"
                        "3. Try a different approach\n\n"
                        "Please let me know how to proceed."
                    )
                    create_user_message(extend_content, state.sm)
                    if state.show_thoughts:
                        await ui.muted(
                            f"\nITERATION LIMIT: Awaiting user guidance at {ctx.max_iterations} iterations"
                        )
                    response_state.awaiting_user_guidance = True
                    # Do not auto-increase max_iterations here (avoid infinite loops)

                i += 1

            # Final buffered read-only tasks (batch)
            await _finalize_buffered_tasks(flush_coordinator, state)

            # SAFETY NET: Ensure all tool calls have responses before returning
            patch_tool_messages("Tool execution completed", state_manager=state_manager)

            # Build fallback synthesis if needed
            if _should_build_fallback(response_state, i, ctx.max_iterations, ctx.fallback_enabled):
                patch_tool_messages("Task incomplete", state_manager=state_manager)
                response_state.has_final_synthesis = True
                comprehensive_output = _build_fallback_output(i, ctx.max_iterations, state)
                wrapper = AgentRunWrapper(
                    agent_run, SimpleResult(comprehensive_output), response_state
                )
                return wrapper

            # Normal path: return a wrapper that carries response_state
            return AgentRunWithState(agent_run, response_state)

    except UserAbortError:
        raise
    except ToolBatchingJSONError as e:
        logger.error("Tool batching JSON error [req=%s]: %s", ctx.request_id, e, exc_info=True)
        patch_tool_messages(f"Tool batching failed: {str(e)[:100]}...", state_manager=state_manager)
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
        patch_tool_messages(
            f"Request processing failed: {str(e)[:100]}...", state_manager=state_manager
        )
        raise
