"""Module: tunacode.core.agents.main

Main agent functionality and coordination for the TunaCode CLI.
Handles agent creation, configuration, and request processing.

CLAUDE_ANCHOR[main-agent-module]: Primary agent orchestration and lifecycle management
"""

# Re-export for backward compatibility
from tunacode.services.mcp import get_mcp_servers

from .agent_components import (
    ToolBuffer,
    check_task_completion,
    extract_and_execute_tool_calls,
    get_model_messages,
    parse_json_tool_calls,
    patch_tool_messages,
)

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

import asyncio
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool  # noqa: F401

from tunacode.core.logging.logger import get_logger

# Import agent components
from .agent_components import (
    AgentRunWithState,
    AgentRunWrapper,
    ResponseState,
    SimpleResult,
    _process_node,
    execute_tools_parallel,
    get_or_create_agent,
)

# Import streaming types with fallback for older versions
try:
    from pydantic_ai.messages import PartDeltaEvent, TextPartDelta

    STREAMING_AVAILABLE = True
except ImportError:
    # Fallback for older pydantic-ai versions
    PartDeltaEvent = None
    TextPartDelta = None
    STREAMING_AVAILABLE = False

from tunacode.core.state import StateManager
from tunacode.exceptions import ToolBatchingJSONError, UserAbortError
from tunacode.types import (
    AgentRun,
    FallbackResponse,
    ModelName,
    ToolCallback,
    UsageTrackerProtocol,
)

# Configure logging
logger = get_logger(__name__)

# Cache for UserPromptPart class to avoid repeated imports
_USER_PROMPT_PART_CLASS = None


def _get_user_prompt_part_class():
    """Get UserPromptPart class with caching and fallback for test environment.

    This function follows DRY principle by centralizing the UserPromptPart
    import logic and caching the result to avoid repeated imports.
    """
    global _USER_PROMPT_PART_CLASS

    if _USER_PROMPT_PART_CLASS is not None:
        return _USER_PROMPT_PART_CLASS

    try:
        import importlib

        messages = importlib.import_module("pydantic_ai.messages")
        _USER_PROMPT_PART_CLASS = getattr(messages, "UserPromptPart", None)

        if _USER_PROMPT_PART_CLASS is None:
            # Fallback for test environment
            class UserPromptPartFallback:
                def __init__(self, content, part_kind):
                    self.content = content
                    self.part_kind = part_kind

            _USER_PROMPT_PART_CLASS = UserPromptPartFallback
    except Exception:
        # Fallback for test environment
        class UserPromptPartFallback:
            def __init__(self, content, part_kind):
                self.content = content
                self.part_kind = part_kind

        _USER_PROMPT_PART_CLASS = UserPromptPartFallback

    return _USER_PROMPT_PART_CLASS


def get_agent_tool() -> tuple[type[Agent], type["Tool"]]:
    """Lazy import for Agent and Tool to avoid circular imports."""
    from pydantic_ai import Agent, Tool

    return Agent, Tool


async def check_query_satisfaction(
    agent: Agent,
    original_query: str,
    response: str,
    state_manager: StateManager,
) -> bool:
    """
    Check if the response satisfies the original query.

    Returns:
        bool: True if query is satisfied, False otherwise
    """
    # For now, always return True to avoid recursive checks
    # The agent should use TUNACODE_TASK_COMPLETE marker instead
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
    # Get or create agent for the model
    agent = get_or_create_agent(model, state_manager)

    # Create a unique request ID for debugging
    import uuid

    request_id = str(uuid.uuid4())[:8]

    # Reset state for new request
    state_manager.session.current_iteration = 0
    state_manager.session.iteration_count = 0
    state_manager.session.tool_calls = []

    # Initialize batch counter if not exists
    if not hasattr(state_manager.session, "batch_counter"):
        state_manager.session.batch_counter = 0

    # Create tool buffer for parallel execution
    tool_buffer = ToolBuffer()

    # Track iterations and productivity
    max_iterations = state_manager.session.user_config.get("settings", {}).get("max_iterations", 15)
    unproductive_iterations = 0
    last_productive_iteration = 0

    # Track response state
    response_state = ResponseState()

    # Get current generation ID for cancellation checking
    gen_id = state_manager.current_generation()

    try:
        # Get message history from session messages
        # Create a copy of the message history to avoid modifying the original
        message_history = list(state_manager.session.messages)

        async with agent.iter(message, message_history=message_history) as agent_run:
            # Process nodes iteratively
            i = 1
            async for node in agent_run:
                # Check if generation is still current before processing node
                if not state_manager.is_current(gen_id):
                    logger.debug(f"Generation {gen_id} invalidated, stopping agent run")
                    break

                state_manager.session.current_iteration = i
                state_manager.session.iteration_count = i

                # Handle token-level streaming for model request nodes
                Agent, _ = get_agent_tool()
                if streaming_callback and STREAMING_AVAILABLE and Agent.is_model_request_node(node):
                    from .stream_utils import stream_worker

                    # Create stream factory function
                    async def make_stream():
                        return node.stream(agent_run.ctx)

                    # Create write callback that filters for text deltas
                    async def write_callback(event):
                        if isinstance(event, PartDeltaEvent) and isinstance(
                            event.delta, TextPartDelta
                        ):
                            if event.delta.content_delta and streaming_callback:
                                await streaming_callback(event.delta.content_delta)

                    # Create and store streaming task
                    stream_task = asyncio.create_task(
                        stream_worker(
                            gen_id=gen_id,
                            make_stream=make_stream,
                            write_callback=write_callback,
                            state_manager=state_manager,
                            logger=logger,
                        )
                    )

                    # Store task reference for cancellation
                    if not hasattr(state_manager.session, "stream_tasks"):
                        state_manager.session.stream_tasks = []
                    state_manager.session.stream_tasks.append(stream_task)

                    try:
                        # Wait for streaming to complete
                        await stream_task
                    except asyncio.CancelledError:
                        # Stream was cancelled
                        logger.debug("Streaming task cancelled")
                        response_state.stream_cancelled = True
                    finally:
                        # Remove task from list
                        if hasattr(state_manager.session, "stream_tasks"):
                            state_manager.session.stream_tasks.remove(stream_task)

                # If stream was cancelled, return early with cancellation response
                if response_state.stream_cancelled:
                    return AgentRunWrapper(
                        wrapped_run=agent_run,
                        fallback_result=FallbackResponse(
                            output="",  # Empty output since streaming was interrupted
                            task_complete=False,
                        ),
                        response_state=response_state,
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

                # Handle empty response by asking user for help instead of giving up
                if empty_response:
                    # Track consecutive empty responses
                    if not hasattr(state_manager.session, "consecutive_empty_responses"):
                        state_manager.session.consecutive_empty_responses = 0
                    state_manager.session.consecutive_empty_responses += 1

                    # IMMEDIATE AGGRESSIVE INTERVENTION on ANY empty response
                    if state_manager.session.consecutive_empty_responses >= 1:
                        # Get context about what was happening
                        last_tools_used = []
                        if state_manager.session.tool_calls:
                            for tc in state_manager.session.tool_calls[-3:]:
                                tool_name = tc.get("tool", "unknown")
                                tool_args = tc.get("args", {})
                                tool_desc = tool_name
                                if tool_name in ["grep", "glob"] and isinstance(tool_args, dict):
                                    pattern = tool_args.get("pattern", "")
                                    tool_desc = f"{tool_name}('{pattern}')"
                                elif tool_name == "read_file" and isinstance(tool_args, dict):
                                    path = tool_args.get("file_path", tool_args.get("filepath", ""))
                                    tool_desc = f"{tool_name}('{path}')"
                                last_tools_used.append(tool_desc)

                        tools_context = (
                            f"Recent tools: {', '.join(last_tools_used)}"
                            if last_tools_used
                            else "No tools used yet"
                        )

                        # AGGRESSIVE prompt - YOU FAILED, TRY HARDER
                        force_action_content = f"""FAILURE DETECTED: You returned {"an " + empty_reason if empty_reason != "empty" else "an empty"} response.

This is UNACCEPTABLE. You FAILED to produce output.

Task: {message[:200]}...
{tools_context}
Current iteration: {i}

TRY AGAIN RIGHT NOW:

1. If your search returned no results → Try a DIFFERENT search pattern
2. If you found what you need → Use TUNACODE_TASK_COMPLETE
3. If you're stuck → EXPLAIN SPECIFICALLY what's blocking you
4. If you need to explore → Use list_dir or broader searches

YOU MUST PRODUCE REAL OUTPUT IN THIS RESPONSE. NO EXCUSES.
EXECUTE A TOOL OR PROVIDE SUBSTANTIAL CONTENT.
DO NOT RETURN ANOTHER EMPTY RESPONSE."""

                        model_request_cls = get_model_messages()[0]
                        # Get UserPromptPart from the cached helper
                        UserPromptPart = _get_user_prompt_part_class()
                        user_prompt_part = UserPromptPart(
                            content=force_action_content,
                            part_kind="user-prompt",
                        )
                        force_message = model_request_cls(
                            parts=[user_prompt_part],
                            kind="request",
                        )
                        state_manager.session.messages.append(force_message)

                        if state_manager.session.show_thoughts:
                            from tunacode.ui import console as ui

                            await ui.warning(
                                "\n⚠️ EMPTY RESPONSE FAILURE - AGGRESSIVE RETRY TRIGGERED"
                            )
                            await ui.muted(f"   Reason: {empty_reason}")
                            await ui.muted(f"   Recent tools: {tools_context}")
                            await ui.muted("   Injecting 'YOU FAILED TRY HARDER' prompt")

                        # Reset counter after aggressive intervention
                        state_manager.session.consecutive_empty_responses = 0
                else:
                    # Reset counter on successful response
                    if hasattr(state_manager.session, "consecutive_empty_responses"):
                        state_manager.session.consecutive_empty_responses = 0

                if hasattr(node, "result") and node.result and hasattr(node.result, "output"):
                    if node.result.output:
                        response_state.has_user_response = True

                # Track productivity - check if any tools were used in this iteration
                iteration_had_tools = False
                if hasattr(node, "model_response"):
                    for part in node.model_response.parts:
                        if hasattr(part, "part_kind") and part.part_kind == "tool-call":
                            iteration_had_tools = True
                            break

                if iteration_had_tools:
                    # Reset unproductive counter
                    unproductive_iterations = 0
                    last_productive_iteration = i
                else:
                    # Increment unproductive counter
                    unproductive_iterations += 1

                # After 3 unproductive iterations, force action
                if unproductive_iterations >= 3 and not response_state.task_completed:
                    no_progress_content = f"""ALERT: No tools executed for {unproductive_iterations} iterations.

Last productive iteration: {last_productive_iteration}
Current iteration: {i}/{max_iterations}
Task: {message[:200]}...

You're describing actions but not executing them. You MUST:

1. If task is COMPLETE: Start response with TUNACODE_TASK_COMPLETE
2. If task needs work: Execute a tool RIGHT NOW (grep, read_file, bash, etc.)
3. If stuck: Explain the specific blocker

NO MORE DESCRIPTIONS. Take ACTION or mark COMPLETE."""

                    model_request_cls = get_model_messages()[0]
                    # Get UserPromptPart from the cached helper
                    UserPromptPart = _get_user_prompt_part_class()
                    user_prompt_part = UserPromptPart(
                        content=no_progress_content,
                        part_kind="user-prompt",
                    )
                    progress_message = model_request_cls(
                        parts=[user_prompt_part],
                        kind="request",
                    )
                    state_manager.session.messages.append(progress_message)

                    if state_manager.session.show_thoughts:
                        from tunacode.ui import console as ui

                        await ui.warning(
                            f"⚠️ NO PROGRESS: {unproductive_iterations} iterations without tool usage"
                        )

                    # Reset counter after intervention
                    unproductive_iterations = 0

                # REMOVED: Recursive satisfaction check that caused empty responses
                # The agent now decides completion using TUNACODE_TASK_COMPLETE marker
                # This eliminates recursive agent calls and gives control back to the agent

                # Store original query for reference
                if not hasattr(state_manager.session, "original_query"):
                    state_manager.session.original_query = message

                # Display iteration progress if thoughts are enabled
                if state_manager.session.show_thoughts:
                    from tunacode.ui import console as ui

                    await ui.muted(f"\nITERATION: {i}/{max_iterations} (Request ID: {request_id})")

                    # Show summary of tools used so far
                    if state_manager.session.tool_calls:
                        tool_summary: dict[str, int] = {}
                        for tc in state_manager.session.tool_calls:
                            tool_name = tc.get("tool", "unknown")
                            tool_summary[tool_name] = tool_summary.get(tool_name, 0) + 1

                        summary_str = ", ".join(
                            [f"{name}: {count}" for name, count in tool_summary.items()]
                        )
                        await ui.muted(f"TOOLS USED: {summary_str}")

                # User clarification: Ask user for guidance when explicitly awaiting
                if response_state.awaiting_user_guidance:
                    # Build a progress summary
                    tool_summary = {}
                    if state_manager.session.tool_calls:
                        for tc in state_manager.session.tool_calls:
                            tool_name = tc.get("tool", "unknown")
                            tool_summary[tool_name] = tool_summary.get(tool_name, 0) + 1

                    tools_used_str = (
                        ", ".join([f"{name}: {count}" for name, count in tool_summary.items()])
                        if tool_summary
                        else "No tools used yet"
                    )

                    # Create user message asking for clarification
                    model_request_cls = get_model_messages()[0]
                    # Get UserPromptPart from the cached helper
                    UserPromptPart = _get_user_prompt_part_class()

                    clarification_content = f"""I need clarification to continue.

Original request: {getattr(state_manager.session, "original_query", "your request")}

Progress so far:
- Iterations: {i}
- Tools used: {tools_used_str}

If the task is complete, I should respond with TUNACODE_TASK_COMPLETE.
Otherwise, please provide specific guidance on what to do next."""

                    user_prompt_part = UserPromptPart(
                        content=clarification_content,
                        part_kind="user-prompt",
                    )
                    clarification_message = model_request_cls(
                        parts=[user_prompt_part],
                        kind="request",
                    )
                    state_manager.session.messages.append(clarification_message)

                    if state_manager.session.show_thoughts:
                        from tunacode.ui import console as ui

                        await ui.muted(
                            "\n🤔 SEEKING CLARIFICATION: Asking user for guidance on task progress"
                        )

                    # Mark that we've asked for user guidance
                    response_state.awaiting_user_guidance = True

                # Check if task is explicitly completed
                if response_state.task_completed:
                    if state_manager.session.show_thoughts:
                        from tunacode.ui import console as ui

                        await ui.success("Task completed successfully")
                    break

                if i >= max_iterations and not response_state.task_completed:
                    # Instead of breaking, ask user if they want to continue
                    # Build progress summary
                    tool_summary = {}
                    if state_manager.session.tool_calls:
                        for tc in state_manager.session.tool_calls:
                            tool_name = tc.get("tool", "unknown")
                            tool_summary[tool_name] = tool_summary.get(tool_name, 0) + 1

                    tools_str = (
                        ", ".join([f"{name}: {count}" for name, count in tool_summary.items()])
                        if tool_summary
                        else "No tools used"
                    )

                    extend_content = f"""I've reached the iteration limit ({max_iterations}).

Progress summary:
- Tools used: {tools_str}
- Iterations completed: {i}

The task appears incomplete. Would you like me to:
1. Continue working (I can extend the limit)
2. Summarize what I've done and stop
3. Try a different approach

Please let me know how to proceed."""

                    # Create user message
                    model_request_cls = get_model_messages()[0]
                    # Get UserPromptPart from the cached helper
                    UserPromptPart = _get_user_prompt_part_class()
                    user_prompt_part = UserPromptPart(
                        content=extend_content,
                        part_kind="user-prompt",
                    )
                    extend_message = model_request_cls(
                        parts=[user_prompt_part],
                        kind="request",
                    )
                    state_manager.session.messages.append(extend_message)

                    if state_manager.session.show_thoughts:
                        from tunacode.ui import console as ui

                        await ui.muted(
                            f"\n📊 ITERATION LIMIT: Asking user for guidance at {max_iterations} iterations"
                        )

                    # Extend the limit temporarily to allow processing the response
                    max_iterations += 5  # Give 5 more iterations to process user guidance
                    response_state.awaiting_user_guidance = True

                # Increment iteration counter
                i += 1

            # Final flush: execute any remaining buffered read-only tools
            if tool_callback and tool_buffer.has_tasks():
                import time

                from tunacode.ui import console as ui

                buffered_tasks = tool_buffer.flush()
                start_time = time.time()

                await ui.muted("\n" + "=" * 60)
                await ui.muted(
                    f"🚀 FINAL BATCH: Executing {len(buffered_tasks)} buffered read-only tools"
                )
                await ui.muted("=" * 60)

                for idx, (part, node) in enumerate(buffered_tasks, 1):
                    tool_desc = f"  [{idx}] {part.tool_name}"
                    if hasattr(part, "args") and isinstance(part.args, dict):
                        if part.tool_name == "read_file" and "file_path" in part.args:
                            tool_desc += f" → {part.args['file_path']}"
                        elif part.tool_name == "grep" and "pattern" in part.args:
                            tool_desc += f" → pattern: '{part.args['pattern']}'"
                            if "include_files" in part.args:
                                tool_desc += f", files: '{part.args['include_files']}'"
                        elif part.tool_name == "list_dir" and "directory" in part.args:
                            tool_desc += f" → {part.args['directory']}"
                        elif part.tool_name == "glob" and "pattern" in part.args:
                            tool_desc += f" → pattern: '{part.args['pattern']}'"
                    await ui.muted(tool_desc)
                await ui.muted("=" * 60)

                await execute_tools_parallel(buffered_tasks, tool_callback)

                elapsed_time = (time.time() - start_time) * 1000
                sequential_estimate = len(buffered_tasks) * 100
                speedup = sequential_estimate / elapsed_time if elapsed_time > 0 else 1.0

                await ui.muted(
                    f"✅ Final batch completed in {elapsed_time:.0f}ms "
                    f"(~{speedup:.1f}x faster than sequential)\n"
                )

            # If we need to add a fallback response, create a wrapper
            # Don't add fallback if task was explicitly completed
            if (
                not response_state.has_user_response
                and not response_state.task_completed
                and i >= max_iterations
                and fallback_enabled
            ):
                patch_tool_messages("Task incomplete", state_manager=state_manager)
                response_state.has_final_synthesis = True

                # Extract context from the agent run
                tool_calls_summary = []
                files_modified = set()
                commands_run = []

                # Analyze message history for context
                for msg in state_manager.session.messages:
                    if hasattr(msg, "parts"):
                        for part in msg.parts:
                            if hasattr(part, "part_kind") and part.part_kind == "tool-call":
                                tool_name = getattr(part, "tool_name", "unknown")
                                tool_calls_summary.append(tool_name)

                                # Track specific operations
                                if tool_name in ["write_file", "update_file"] and hasattr(
                                    part, "args"
                                ):
                                    if isinstance(part.args, dict) and "file_path" in part.args:
                                        files_modified.add(part.args["file_path"])
                                elif tool_name in ["run_command", "bash"] and hasattr(part, "args"):
                                    if isinstance(part.args, dict) and "command" in part.args:
                                        commands_run.append(part.args["command"])

                # Build fallback response with context
                fallback = FallbackResponse(
                    summary="Reached maximum iterations without producing a final response.",
                    progress=f"Completed {i} iterations (limit: {max_iterations})",
                )

                # Get verbosity setting
                verbosity = state_manager.session.user_config.get("settings", {}).get(
                    "fallback_verbosity", "normal"
                )

                if verbosity in ["normal", "detailed"]:
                    # Add what was attempted
                    if tool_calls_summary:
                        tool_counts: dict[str, int] = {}
                        for tool in tool_calls_summary:
                            tool_counts[tool] = tool_counts.get(tool, 0) + 1

                        fallback.issues.append(f"Executed {len(tool_calls_summary)} tool calls:")
                        for tool, count in sorted(tool_counts.items()):
                            fallback.issues.append(f"  • {tool}: {count}x")

                    if verbosity == "detailed":
                        if files_modified:
                            fallback.issues.append(f"\nFiles modified ({len(files_modified)}):")
                            for f in sorted(files_modified)[:5]:  # Limit to 5 files
                                fallback.issues.append(f"  • {f}")
                            if len(files_modified) > 5:
                                fallback.issues.append(
                                    f"  • ... and {len(files_modified) - 5} more"
                                )

                        if commands_run:
                            fallback.issues.append(f"\nCommands executed ({len(commands_run)}):")
                            for cmd in commands_run[:3]:  # Limit to 3 commands
                                # Truncate long commands
                                display_cmd = cmd if len(cmd) <= 60 else cmd[:57] + "..."
                                fallback.issues.append(f"  • {display_cmd}")
                            if len(commands_run) > 3:
                                fallback.issues.append(f"  • ... and {len(commands_run) - 3} more")

                # Add helpful next steps
                fallback.next_steps.append(
                    "The task may be too complex - try breaking it into smaller steps"
                )
                fallback.next_steps.append(
                    "Check the output above for any errors or partial progress"
                )
                if files_modified:
                    fallback.next_steps.append(
                        "Review modified files to see what changes were made"
                    )

                # Create comprehensive output
                output_parts = [fallback.summary, ""]

                if fallback.progress:
                    output_parts.append(f"Progress: {fallback.progress}")

                if fallback.issues:
                    output_parts.append("\nWhat happened:")
                    output_parts.extend(fallback.issues)

                if fallback.next_steps:
                    output_parts.append("\nSuggested next steps:")
                    for step in fallback.next_steps:
                        output_parts.append(f"  • {step}")

                comprehensive_output = "\n".join(output_parts)

                # Create a wrapper object that mimics AgentRun with the required attributes
                wrapper = AgentRunWrapper(
                    agent_run, SimpleResult(comprehensive_output), response_state
                )
                return wrapper

            # For non-fallback cases, we still need to handle the response_state
            # Create a minimal wrapper just to add response_state
            state_wrapper = AgentRunWithState(agent_run, response_state)
            return state_wrapper

    except asyncio.CancelledError:
        # Handle cancellation gracefully without error messages
        logger.debug("Agent task cancelled by user")
        # Don't print completion messages or errors
        raise
    except UserAbortError:
        raise
    except ToolBatchingJSONError as e:
        logger.error(f"Tool batching JSON error: {e}", exc_info=True)
        # Patch orphaned tool messages with error
        patch_tool_messages(f"Tool batching failed: {str(e)[:100]}...", state_manager=state_manager)
        # Re-raise to be handled by caller
        raise
    except Exception as e:
        logger.error(f"Error in process_request: {e}", exc_info=True)
        # Patch orphaned tool messages with generic error
        patch_tool_messages(
            f"Request processing failed: {str(e)[:100]}...", state_manager=state_manager
        )
        # Re-raise to be handled by caller
        raise
