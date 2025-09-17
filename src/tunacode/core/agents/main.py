"""Module: tunacode.core.agents.main

Main agent functionality and coordination for the TunaCode CLI.
Handles agent creation, configuration, and request processing.

CLAUDE_ANCHOR[main-agent-module]: Primary agent orchestration and lifecycle management
"""

import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool  # noqa: F401

from tunacode.constants import UI_THINKING_MESSAGE
from tunacode.core.agents.utils import get_agent_tool
from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import ToolBatchingJSONError, UserAbortError
from tunacode.services.mcp import get_mcp_servers
from tunacode.types import (
    AgentRun,
    ModelName,
    ToolCallback,
    UsageTrackerProtocol,
)
from tunacode.ui.tool_descriptions import get_batch_description

# Import agent components
from .agent_components import (
    AgentRunWithState,
    AgentRunWrapper,
    ResponseState,
    SimpleResult,
    ToolBuffer,
    _process_node,
    check_task_completion,
    create_empty_response_message,
    create_fallback_response,
    create_progress_summary,
    create_user_message,
    execute_tools_parallel,
    extract_and_execute_tool_calls,
    format_fallback_output,
    get_model_messages,
    get_or_create_agent,
    get_recent_tools_context,
    get_tool_summary,
    parse_json_tool_calls,
    patch_tool_messages,
)
from .agent_components.streaming import stream_model_request_node

# Import streaming types with fallback for older versions
try:
    from pydantic_ai.messages import PartDeltaEvent, TextPartDelta

    STREAMING_AVAILABLE = True
except ImportError:
    PartDeltaEvent = None
    TextPartDelta = None
    STREAMING_AVAILABLE = False

# Configure logging
logger = get_logger(__name__)

# Iteration control constants
DEFAULT_MAX_ITERATIONS = 15
EMPTY_RESPONSE_THRESHOLD = 1
NO_PROGRESS_ITERATION_THRESHOLD = 3
ITERATION_EXTENSION_INCREMENT = 5
FAILURE_INDICATORS = ("error", "unable", "cannot", "can't", "failed")


@dataclass
class RequestContext:
    """Ephemeral request-level counters and diagnostics."""

    message: str
    request_id: str
    max_iterations: int
    iteration_index: int = 1
    last_completed_iteration: int = 0
    unproductive_iterations: int = 0
    last_productive_iteration: int = 0

    def record_tool_activity(self, used_tools: bool) -> None:
        """Track whether the current iteration executed any tools."""

        if used_tools:
            self.unproductive_iterations = 0
            self.last_productive_iteration = self.iteration_index
        else:
            self.unproductive_iterations += 1

    def should_force_action(self) -> bool:
        """Determine if we should inject a forced-action prompt."""

        return self.unproductive_iterations >= NO_PROGRESS_ITERATION_THRESHOLD

    def reset_unproductive_counter(self) -> None:
        """Reset the no-progress counter after injecting guidance."""

        self.unproductive_iterations = 0

    def build_force_action_prompt(self) -> str:
        """Create the corrective message for unproductive iterations."""

        return f"""ALERT: No tools executed for {self.unproductive_iterations} iterations.

Last productive iteration: {self.last_productive_iteration}
Current iteration: {self.iteration_index}/{self.max_iterations}
Task: {self.message[:200]}...

You're describing actions but not executing them. You MUST:

1. If task is COMPLETE: Start response with TUNACODE DONE:
2. If task needs work: Execute a tool RIGHT NOW (grep, read_file, bash, etc.)
3. If stuck: Explain the specific blocker

NO MORE DESCRIPTIONS. Take ACTION or mark COMPLETE."""

    def reached_iteration_limit(self, task_completed: bool) -> bool:
        """Check if we've hit the iteration cap without finishing."""

        return self.iteration_index >= self.max_iterations and not task_completed

    def extend_iteration_limit(self) -> None:
        """Extend the iteration budget when the user approves."""

        self.max_iterations += ITERATION_EXTENSION_INCREMENT

    def mark_iteration_complete(self) -> None:
        """Record that the current iteration has finished."""

        self.last_completed_iteration = self.iteration_index
        self.iteration_index += 1

    @property
    def executed_iterations(self) -> int:
        """Return the count of fully executed iterations."""

        return self.last_completed_iteration


class SessionController:
    """Encapsulate session mutations for better observability."""

    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager

    @property
    def session(self):
        return self._state_manager.session

    def reset_for_request(self) -> None:
        self._state_manager.reset_request_tracking()
        self._state_manager.ensure_batch_counter()

    def attach_request(self, request_id: str) -> None:
        try:
            self._state_manager.set_request_context(request_id)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.debug("Unable to attach request id to session: %s", exc, exc_info=True)

    def remember_original_query(self, message: str) -> None:
        self._state_manager.remember_original_query(message)

    def update_iteration(self, iteration_index: int) -> None:
        self._state_manager.update_iteration(iteration_index)

    def increment_empty_responses(self) -> int:
        return self._state_manager.increment_empty_response_counter()

    def reset_empty_responses(self) -> None:
        self._state_manager.reset_empty_response_counter()

    def get_max_iterations(self) -> int:
        settings = self.session.user_config.get("settings", {})
        return int(settings.get("max_iterations", DEFAULT_MAX_ITERATIONS))

    def show_thoughts(self) -> bool:
        return bool(self.session.show_thoughts)


@lru_cache(maxsize=1)
def _get_ui_console():
    """Memoized accessor for the console module to avoid repeated imports."""

    from tunacode.ui import console as ui

    return ui

__all__ = [
    "ToolBuffer",
    "check_task_completion",
    "extract_and_execute_tool_calls",
    "get_model_messages",
    "parse_json_tool_calls",
    "patch_tool_messages",
    "get_mcp_servers",
    "check_query_satisfaction",
    "process_request",
    "get_or_create_agent",
    "_process_node",
    "ResponseState",
    "SimpleResult",
    "AgentRunWrapper",
    "AgentRunWithState",
    "execute_tools_parallel",
    "get_agent_tool",
]


async def check_query_satisfaction(
    agent: Agent,
    original_query: str,
    response: str,
    state_manager: StateManager,
) -> bool:
    """Evaluate whether an agent response satisfies the user's request."""

    completion_detected, _ = check_task_completion(response)
    if completion_detected:
        return True

    if state_manager.is_plan_mode():
        return False

    normalized = response.strip().lower()
    if not normalized:
        return False

    if any(indicator in normalized for indicator in FAILURE_INDICATORS):
        return False

    return True


async def process_request(
    message: str,
    model: ModelName,
    state_manager: StateManager,
    tool_callback: Optional[ToolCallback] = None,
    streaming_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    usage_tracker: Optional[UsageTrackerProtocol] = None,
    fallback_enabled: bool = True,
) -> AgentRun:
    """
    Process a single request to the agent.

    CLAUDE_ANCHOR[process-request-entry]: Main entry point for all agent requests

    Args:
        message: The user's request
        model: The model to use
        state_manager: State manager instance
        tool_callback: Optional callback for tool execution
        streaming_callback: Optional callback for streaming responses
        usage_tracker: Optional usage tracker
        fallback_enabled: Whether to enable fallback responses

    Returns:
        AgentRun or wrapper with result
    """

    agent = get_or_create_agent(model, state_manager)

    session_controller = SessionController(state_manager)
    session_controller.reset_for_request()

    request_id = _generate_request_id()
    session_controller.attach_request(request_id)
    session_controller.remember_original_query(message)

    request_context = RequestContext(
        message=message,
        request_id=request_id,
        max_iterations=session_controller.get_max_iterations(),
    )

    tool_buffer = ToolBuffer()
    response_state = ResponseState()

    try:
        message_history = list(session_controller.session.messages)

        async with agent.iter(message, message_history=message_history) as agent_run:
            await _process_agent_run(
                agent_run,
                agent,
                request_context,
                session_controller,
                state_manager,
                tool_buffer,
                response_state,
                tool_callback,
                streaming_callback,
                usage_tracker,
            )

            return await _finalize_agent_run(
                agent_run,
                request_context,
                response_state,
                state_manager,
                tool_buffer,
                tool_callback,
                fallback_enabled,
            )

    except UserAbortError:
        raise
    except ToolBatchingJSONError as exc:
        logger.error("Tool batching JSON error: %s", exc, exc_info=True)
        patch_tool_messages(
            f"Tool batching failed: {str(exc)[:100]}...", state_manager=state_manager
        )
        raise
    except Exception as exc:
        safe_iter = getattr(session_controller.session, "current_iteration", "?")
        logger.error(
            "Error in process_request [req=%s iter=%s]: %s",
            request_id,
            safe_iter,
            exc,
            exc_info=True,
        )
        patch_tool_messages(
            f"Request processing failed: {str(exc)[:100]}...", state_manager=state_manager
        )
        raise


async def _process_agent_run(
    agent_run: AgentRun,
    agent: Agent,
    request_context: RequestContext,
    session_controller: SessionController,
    state_manager: StateManager,
    tool_buffer: ToolBuffer,
    response_state: ResponseState,
    tool_callback: Optional[ToolCallback],
    streaming_callback: Optional[Callable[[str], Awaitable[None]]],
    usage_tracker: Optional[UsageTrackerProtocol],
) -> None:
    async for node in agent_run:
        session_controller.update_iteration(request_context.iteration_index)

        if streaming_callback and STREAMING_AVAILABLE and Agent.is_model_request_node(node):
            await stream_model_request_node(
                node,
                agent_run.ctx,
                state_manager,
                streaming_callback,
                request_context.request_id,
                request_context.iteration_index,
            )

        empty_response, empty_reason = await _process_node(
            node,
            tool_callback,
            state_manager,
            tool_buffer,
            streaming_callback,
            usage_tracker,
            response_state,
        )

        if empty_response:
            empty_count = session_controller.increment_empty_responses()
            if empty_count >= EMPTY_RESPONSE_THRESHOLD:
                await _handle_empty_response(
                    request_context,
                    empty_reason,
                    state_manager,
                    session_controller,
                )
                session_controller.reset_empty_responses()
        else:
            session_controller.reset_empty_responses()

        if getattr(getattr(node, "result", None), "output", None):
            response_state.has_user_response = True

        iteration_had_tools = _detect_tool_usage(node)
        request_context.record_tool_activity(iteration_had_tools)

        if request_context.should_force_action() and not response_state.task_completed:
            await _handle_no_progress(request_context, state_manager, session_controller)
            request_context.reset_unproductive_counter()

        if session_controller.show_thoughts():
            await _emit_iteration_diagnostics(request_context, session_controller)

        if response_state.awaiting_user_guidance:
            await _handle_user_clarification(request_context, state_manager, session_controller)

        if response_state.task_completed:
            request_context.mark_iteration_complete()
            if session_controller.show_thoughts():
                ui = _get_ui_console()
                await ui.success("Task completed successfully")
            break

        if request_context.reached_iteration_limit(response_state.task_completed):
            await _handle_iteration_extension(request_context, state_manager, session_controller)
            request_context.extend_iteration_limit()
            response_state.awaiting_user_guidance = True

        request_context.mark_iteration_complete()


async def _finalize_agent_run(
    agent_run: AgentRun,
    request_context: RequestContext,
    response_state: ResponseState,
    state_manager: StateManager,
    tool_buffer: ToolBuffer,
    tool_callback: Optional[ToolCallback],
    fallback_enabled: bool,
) -> AgentRun:
    await _flush_tool_buffer(tool_buffer, tool_callback, state_manager)

    executed_iterations = request_context.executed_iterations

    if (
        fallback_enabled
        and not response_state.has_user_response
        and not response_state.task_completed
        and executed_iterations >= request_context.max_iterations
    ):
        patch_tool_messages("Task incomplete", state_manager=state_manager)
        response_state.has_final_synthesis = True

        verbosity = state_manager.session.user_config.get("settings", {}).get(
            "fallback_verbosity", "normal"
        )
        fallback = create_fallback_response(
            executed_iterations,
            request_context.max_iterations,
            state_manager.session.tool_calls,
            state_manager.session.messages,
            verbosity,
        )
        comprehensive_output = format_fallback_output(fallback)
        return AgentRunWrapper(agent_run, SimpleResult(comprehensive_output), response_state)

    return AgentRunWithState(agent_run, response_state)


async def _handle_empty_response(
    request_context: RequestContext,
    empty_reason: Optional[str],
    state_manager: StateManager,
    session_controller: SessionController,
) -> None:
    reason = empty_reason or "No response generated"
    force_action_content = create_empty_response_message(
        request_context.message,
        reason,
        session_controller.session.tool_calls,
        request_context.iteration_index,
        state_manager,
    )
    create_user_message(force_action_content, state_manager)

    if session_controller.show_thoughts():
        ui = _get_ui_console()
        await ui.warning("\nEMPTY RESPONSE FAILURE - AGGRESSIVE RETRY TRIGGERED")
        await ui.muted(f"   Reason: {reason}")
        await ui.muted(
            "\nSEEKING CLARIFICATION: Asking user for guidance on task progress"
        )
        await ui.muted("   Injecting retry guidance prompt")


async def _handle_no_progress(
    request_context: RequestContext,
    state_manager: StateManager,
    session_controller: SessionController,
) -> None:
    create_user_message(request_context.build_force_action_prompt(), state_manager)

    if session_controller.show_thoughts():
        ui = _get_ui_console()
        await ui.warning(
            f"NO PROGRESS: {request_context.unproductive_iterations} iterations without tool usage"
        )


async def _emit_iteration_diagnostics(
    request_context: RequestContext, session_controller: SessionController
) -> None:
    ui = _get_ui_console()
    await ui.muted(
        f"\nITERATION: {request_context.iteration_index}/{request_context.max_iterations} "
        f"(Request ID: {request_context.request_id})"
    )

    if session_controller.session.tool_calls:
        tool_summary = get_tool_summary(session_controller.session.tool_calls)
        summary_str = ", ".join([f"{name}: {count}" for name, count in tool_summary.items()])
        await ui.muted(f"TOOLS USED: {summary_str}")


async def _handle_user_clarification(
    request_context: RequestContext,
    state_manager: StateManager,
    session_controller: SessionController,
) -> None:
    _, tools_used_str = create_progress_summary(session_controller.session.tool_calls)
    original_query = session_controller.session.original_query or request_context.message

    clarification_content = f"""I need clarification to continue.

Original request: {original_query}

Progress so far:
- Iterations: {request_context.iteration_index}
- Tools used: {tools_used_str}

If the task is complete, I should respond with TUNACODE DONE:
Otherwise, please provide specific guidance on what to do next."""

    create_user_message(clarification_content, state_manager)

    if session_controller.show_thoughts():
        ui = _get_ui_console()
        await ui.muted(
            "\nSEEKING CLARIFICATION: Asking user for guidance on task progress"
        )


async def _handle_iteration_extension(
    request_context: RequestContext,
    state_manager: StateManager,
    session_controller: SessionController,
) -> None:
    _, tools_str = create_progress_summary(session_controller.session.tool_calls)
    tools_str = tools_str if tools_str != "No tools used yet" else "No tools used"

    extend_content = f"""I've reached the iteration limit ({request_context.max_iterations}).

Progress summary:
- Tools used: {tools_str}
- Iterations completed: {request_context.iteration_index}

The task appears incomplete. Would you like me to:
1. Continue working (I can extend the limit)
2. Summarize what I've done and stop
3. Try a different approach

Please let me know how to proceed."""

    create_user_message(extend_content, state_manager)

    if session_controller.show_thoughts():
        ui = _get_ui_console()
        await ui.muted(
            f"\nITERATION LIMIT: Asking user for guidance at {request_context.max_iterations} iterations"
        )


async def _flush_tool_buffer(
    tool_buffer: ToolBuffer,
    tool_callback: Optional[ToolCallback],
    state_manager: StateManager,
) -> None:
    if not tool_callback or not tool_buffer.has_tasks():
        return

    ui = _get_ui_console()
    buffered_tasks = tool_buffer.flush()
    start_time = time.time()

    tool_names = [getattr(part, "tool_name", "") for part, _ in buffered_tasks]
    batch_msg = get_batch_description(len(buffered_tasks), tool_names)
    await ui.update_spinner_message(
        f"[bold #00d7ff]{batch_msg}...[/bold #00d7ff]", state_manager
    )

    await ui.muted("\n" + "=" * 60)
    await ui.muted(
        f"FINAL BATCH: Executing {len(buffered_tasks)} buffered read-only tools"
    )
    await ui.muted("=" * 60)

    for idx, (part, _) in enumerate(buffered_tasks, 1):
        tool_name = getattr(part, "tool_name", "unknown")
        tool_desc = f"  [{idx}] {tool_name}"
        if hasattr(part, "args") and isinstance(part.args, dict):
            args = part.args
            if tool_name == "read_file" and "file_path" in args:
                tool_desc += f" → {args['file_path']}"
            elif tool_name == "grep" and "pattern" in args:
                tool_desc += f" → pattern: '{args['pattern']}'"
                if "include_files" in args:
                    tool_desc += f", files: '{args['include_files']}'"
            elif tool_name == "list_dir" and "directory" in args:
                tool_desc += f" → {args['directory']}"
            elif tool_name == "glob" and "pattern" in args:
                tool_desc += f" → pattern: '{args['pattern']}'"
        await ui.muted(tool_desc)
    await ui.muted("=" * 60)

    await execute_tools_parallel(buffered_tasks, tool_callback)

    elapsed_time = (time.time() - start_time) * 1000
    sequential_estimate = len(buffered_tasks) * 100
    speedup = sequential_estimate / elapsed_time if elapsed_time > 0 else 1.0

    await ui.muted(
        f"Final batch completed in {elapsed_time:.0f}ms (~{speedup:.1f}x faster than sequential)\n"
    )

    await ui.update_spinner_message(UI_THINKING_MESSAGE, state_manager)


def _detect_tool_usage(node: Any) -> bool:
    model_response = getattr(node, "model_response", None)
    if not model_response:
        return False

    parts = getattr(model_response, "parts", None)
    if not parts:
        return False

    for part in parts:
        if getattr(part, "part_kind", None) == "tool-call":
            return True
    return False


def _generate_request_id() -> str:
    return str(uuid.uuid4())[:8]
