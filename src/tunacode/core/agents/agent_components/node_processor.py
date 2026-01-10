"""Node processing functionality for agent responses."""

from collections.abc import Awaitable, Callable
from typing import Any, cast

from tunacode.constants import (
    ERROR_TOOL_ARGS_MISSING,
    ERROR_TOOL_CALL_ID_MISSING,
    UI_COLORS,
)
from tunacode.core.logging import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import StateError, UserAbortError
from tunacode.types import AgentState, ToolArgs, ToolCallId
from tunacode.utils.ui import DotDict

from .response_state import ResponseState
from .task_completion import check_task_completion
from .tool_buffer import ToolBuffer
from .truncation_checker import check_for_truncation

colors = DotDict(UI_COLORS)

PART_KIND_TOOL_CALL = "tool-call"
PART_KIND_TOOL_RETURN = "tool-return"
UNKNOWN_TOOL_NAME = "unknown"


async def _normalize_tool_args(raw_args: Any) -> ToolArgs:
    from tunacode.utils.parsing.command_parser import parse_args

    parsed_args = await parse_args(raw_args)
    return cast(ToolArgs, parsed_args)


async def _record_tool_call_args(part: Any, state_manager: StateManager) -> ToolArgs:
    raw_args = getattr(part, "args", {})
    parsed_args = await _normalize_tool_args(raw_args)
    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    if tool_call_id:
        state_manager.session.tool_call_args_by_id[tool_call_id] = parsed_args
    return parsed_args


def _consume_tool_call_args(part: Any, state_manager: StateManager) -> ToolArgs:
    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    if not tool_call_id:
        raise StateError(ERROR_TOOL_CALL_ID_MISSING)
    tool_call_args = state_manager.session.tool_call_args_by_id.pop(tool_call_id, None)
    if tool_call_args is None:
        raise StateError(ERROR_TOOL_ARGS_MISSING.format(tool_call_id=tool_call_id))
    return tool_call_args


def _has_tool_calls(parts: list[Any]) -> bool:
    return any(getattr(part, "part_kind", None) == PART_KIND_TOOL_CALL for part in parts)


PART_KIND_TEXT = "text"


async def _extract_fallback_tool_calls(
    parts: list[Any],
    state_manager: StateManager,
    response_state: "ResponseState | None",
) -> list[tuple[Any, ToolArgs]]:
    """Extract tool calls from text parts using fallback parsing.

    Called when no structured tool calls (part_kind == "tool-call") are found.
    Attempts to parse embedded tool calls from text content.

    Args:
        parts: Model response parts to scan
        state_manager: For recording tool call args
        response_state: For state transitions

    Returns:
        List of (part, args) tuples for found tool calls
    """
    from pydantic_ai.messages import ToolCallPart

    from tunacode.utils.parsing.tool_parser import (
        has_potential_tool_call,
        parse_tool_calls_from_text,
    )

    results: list[tuple[Any, ToolArgs]] = []

    # Collect text content from text parts
    text_content = ""
    for part in parts:
        part_kind = getattr(part, "part_kind", None)
        if part_kind == PART_KIND_TEXT:
            content = getattr(part, "content", "")
            if content:
                text_content += content + "\n"

    # Quick check before expensive parsing
    if not has_potential_tool_call(text_content):
        return results

    # Parse tool calls from combined text
    parsed_calls = parse_tool_calls_from_text(text_content)

    if not parsed_calls:
        return results

    # Transition to TOOL_EXECUTION on finding fallback tools
    if response_state and response_state.can_transition_to(AgentState.TOOL_EXECUTION):
        response_state.transition_to(AgentState.TOOL_EXECUTION)

    # Convert ParsedToolCall to ToolCallPart objects
    for parsed in parsed_calls:
        # Create a ToolCallPart compatible with existing infrastructure
        part = ToolCallPart(
            tool_name=parsed.tool_name,
            args=parsed.args,
            tool_call_id=parsed.tool_call_id,
        )

        # Record args for later retrieval
        tool_args = await _normalize_tool_args(parsed.args)
        state_manager.session.tool_call_args_by_id[parsed.tool_call_id] = tool_args

        results.append((part, tool_args))

    return results


def _update_token_usage(model_response: Any, state_manager: StateManager) -> None:
    usage = getattr(model_response, "usage", None)
    if not usage:
        return

    prompt_tokens = getattr(usage, "request_tokens", 0) or 0
    completion_tokens = getattr(usage, "response_tokens", 0) or 0
    cached_tokens = getattr(usage, "cached_tokens", 0) or 0

    session = state_manager.session
    session.last_call_usage["prompt_tokens"] = prompt_tokens
    session.last_call_usage["completion_tokens"] = completion_tokens

    from tunacode.configuration.pricing import calculate_cost, get_model_pricing

    pricing = get_model_pricing(session.current_model)
    if pricing is not None:
        non_cached_input = max(0, prompt_tokens - cached_tokens)
        cost = calculate_cost(pricing, non_cached_input, cached_tokens, completion_tokens)
        session.last_call_usage["cost"] = cost
        session.session_total_usage["cost"] += cost
    else:
        session.last_call_usage["cost"] = 0.0

    session.session_total_usage["prompt_tokens"] += prompt_tokens
    session.session_total_usage["completion_tokens"] += completion_tokens


async def _process_node(
    node,
    tool_callback: Callable | None,
    state_manager: StateManager,
    tool_buffer: ToolBuffer | None = None,
    streaming_callback: Callable[[str], Awaitable[None]] | None = None,
    response_state: ResponseState | None = None,
    tool_result_callback: Callable[..., None] | None = None,
    tool_start_callback: Callable[[str], None] | None = None,
) -> tuple[bool, str | None]:
    """Process a single node from the agent response.

    Returns:
        tuple: (is_empty: bool, reason: Optional[str]) - True if empty/problematic
               response detected, with reason being one of: "empty", "truncated",
               "intention_without_action"
    """
    # Use the original callback directly - parallel execution will be handled differently
    buffering_callback = tool_callback
    empty_response_detected = False
    has_non_empty_content = False
    appears_truncated = False
    has_intention = False
    has_tool_calls = False

    # Transition to ASSISTANT at the start of node processing
    if response_state and response_state.can_transition_to(AgentState.ASSISTANT):
        response_state.transition_to(AgentState.ASSISTANT)

    if hasattr(node, "request"):
        state_manager.session.messages.append(node.request)

        # Display tool returns from previous iteration (they're in node.request)
        if tool_result_callback and hasattr(node.request, "parts"):
            for part in node.request.parts:
                part_kind = getattr(part, "part_kind", None)
                if part_kind != PART_KIND_TOOL_RETURN:
                    continue
                tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
                tool_args = _consume_tool_call_args(part, state_manager)
                content = getattr(part, "content", None)
                result_str = str(content) if content is not None else None
                tool_result_callback(
                    tool_name=tool_name,
                    status="completed",
                    args=tool_args,
                    result=result_str,
                )

    if hasattr(node, "thought") and node.thought:
        state_manager.session.messages.append({"thought": node.thought})

    if hasattr(node, "model_response"):
        state_manager.session.messages.append(node.model_response)

        _update_token_usage(node.model_response, state_manager)
        # Update context window token count
        state_manager.session.update_token_count()

        # Check for task completion marker in response content
        if response_state:
            has_non_empty_content = False
            appears_truncated = False
            all_content_parts = []

            # First, check if there are any tool calls in this response
            response_parts = node.model_response.parts
            has_queued_tools = _has_tool_calls(response_parts)

            for part in response_parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    # Check if we have any non-empty content
                    if part.content.strip():
                        has_non_empty_content = True
                        all_content_parts.append(part.content)

                    is_complete, cleaned_content = check_task_completion(part.content)
                    if is_complete:
                        # Validate completion - check for premature completion
                        if has_queued_tools:
                            # Agent is trying to complete with pending tools!
                            # Don't mark as complete - let the tools run first
                            # Update the content to remove the marker but don't set task_completed
                            part.content = cleaned_content
                        else:
                            # Check if content suggests pending actions
                            combined_text = " ".join(all_content_parts).lower()
                            pending_phrases = [
                                "let me",
                                "i'll check",
                                "i will",
                                "going to",
                                "about to",
                                "need to check",
                                "let's check",
                                "i should",
                                "need to find",
                                "let me see",
                                "i'll look",
                                "let me search",
                                "let me find",
                            ]
                            has_pending_intention = any(
                                phrase in combined_text for phrase in pending_phrases
                            )

                            # Also check for action verbs at end of content
                            # suggesting incomplete action
                            action_endings = [
                                "checking",
                                "searching",
                                "looking",
                                "finding",
                                "reading",
                                "analyzing",
                            ]
                            ends_with_action = any(
                                combined_text.rstrip().endswith(ending) for ending in action_endings
                            )

                            early_with_pending = (
                                has_pending_intention or ends_with_action
                            ) and state_manager.session.iteration_count <= 1

                            # Always strip the marker from content
                            part.content = cleaned_content

                            if not early_with_pending:
                                response_state.transition_to(AgentState.RESPONSE)
                                response_state.set_completion_detected(True)
                                response_state.has_user_response = True
                        break

            # Check for truncation patterns
            if all_content_parts:
                combined_content = " ".join(all_content_parts).strip()
                appears_truncated = check_for_truncation(combined_content)

            # If we only got empty content and no tool calls, we should NOT consider this
            # a valid response
            # This prevents the agent from stopping when it gets empty responses
            if not has_non_empty_content and not has_queued_tools:
                # Empty response with no tools - keep going
                empty_response_detected = True

            # Check if response appears truncated
            elif appears_truncated and not has_queued_tools:
                # Truncated response detected
                empty_response_detected = True

        # Process tool calls
        await _process_tool_calls(
            node,
            buffering_callback,
            state_manager,
            tool_buffer,
            response_state,
            tool_result_callback,
            tool_start_callback,
        )

    # If there were no tools and we processed a model response, transition to RESPONSE
    # Only transition if not already completed (set by completion marker path)
    if (
        response_state
        and response_state.can_transition_to(AgentState.RESPONSE)
        and not response_state.is_completed()
    ):
        response_state.transition_to(AgentState.RESPONSE)

    # Determine empty response reason
    if empty_response_detected:
        if appears_truncated:
            return True, "truncated"
        else:
            return True, "empty"

    # Check for intention without action
    if has_intention and not has_tool_calls and not has_non_empty_content:
        return True, "intention_without_action"

    return False, None


async def _process_tool_calls(
    node: Any,
    tool_callback: Callable | None,
    state_manager: StateManager,
    tool_buffer: ToolBuffer | None,
    response_state: ResponseState | None,
    tool_result_callback: Callable[..., None] | None = None,
    tool_start_callback: Callable[[str], None] | None = None,
) -> None:
    """
    Process tool calls from the node using smart batching strategy.

    Smart batching optimization:
    - Collect all read-only tools into a single batch (regardless of write tools in between)
    - Execute all read-only tools in one parallel batch
    - Execute write/execute tools sequentially in their original order

    This maximizes parallel execution efficiency by avoiding premature buffer flushes.
    """
    from tunacode.constants import READ_ONLY_TOOLS

    logger = get_logger()

    # Track if we're processing tool calls
    is_processing_tools = False

    # Phase 1: Collect and categorize all tools
    read_only_tasks = []
    research_agent_tasks = []
    write_execute_tasks = []
    tool_call_records: list[tuple[Any, ToolArgs]] = []

    for part in node.model_response.parts:
        part_kind = getattr(part, "part_kind", None)
        if part_kind != PART_KIND_TOOL_CALL:
            continue
        is_processing_tools = True
        # Transition to TOOL_EXECUTION on first tool call
        if response_state and response_state.can_transition_to(AgentState.TOOL_EXECUTION):
            response_state.transition_to(AgentState.TOOL_EXECUTION)

        tool_args = await _record_tool_call_args(part, state_manager)
        tool_call_records.append((part, tool_args))

        if tool_callback:
            # Categorize: research agent vs read-only vs write/execute
            if part.tool_name == "research_codebase":
                research_agent_tasks.append((part, node))
            elif part.tool_name in READ_ONLY_TOOLS:
                read_only_tasks.append((part, node))
            else:
                write_execute_tasks.append((part, node))

    # Phase 1.5: FALLBACK - Parse text parts if no structured tool calls found
    # Handles non-standard formats like Qwen2-style XML, Hermes-style, etc.
    if not tool_call_records and tool_callback:
        fallback_tool_calls = await _extract_fallback_tool_calls(
            node.model_response.parts,
            state_manager,
            response_state,
        )

        if fallback_tool_calls:
            is_processing_tools = True
            for part, tool_args in fallback_tool_calls:
                tool_call_records.append((part, tool_args))
                # Categorize fallback tools same as structured ones
                if part.tool_name == "research_codebase":
                    research_agent_tasks.append((part, node))
                elif part.tool_name in READ_ONLY_TOOLS:
                    read_only_tasks.append((part, node))
                else:
                    write_execute_tasks.append((part, node))

    # Phase 2: Execute research agent
    if research_agent_tasks and tool_callback:
        from .tool_executor import execute_tools_parallel

        logger.debug(f"Phase 2: research agent ({len(research_agent_tasks)} calls)")

        if tool_start_callback:
            tool_start_callback("research")

        await execute_tools_parallel(research_agent_tasks, tool_callback)

    # Phase 3: Execute read-only tools in ONE parallel batch
    if read_only_tasks and tool_callback:
        from .tool_executor import execute_tools_parallel

        logger.debug(f"Phase 3: read-only batch ({len(read_only_tasks)} calls)")

        batch_id = getattr(state_manager.session, "batch_counter", 0) + 1
        state_manager.session.batch_counter = batch_id

        if tool_start_callback:
            names = [p.tool_name for p, _ in read_only_tasks[:3]]
            suffix = "..." if len(read_only_tasks) > 3 else ""
            tool_start_callback(", ".join(names) + suffix)

        await execute_tools_parallel(read_only_tasks, tool_callback)

    # Phase 4: Execute write/execute tools sequentially
    if write_execute_tasks:
        logger.debug(f"Phase 4: write/execute ({len(write_execute_tasks)} calls)")

    for part, node in write_execute_tasks:
        if tool_start_callback:
            tool_start_callback(part.tool_name)

        try:
            await tool_callback(part, node)
        except UserAbortError:
            raise

    # Track tool calls in session
    if tool_call_records:
        # Extract tool information for tracking
        for part, tool_args in tool_call_records:
            tool_call_id = getattr(part, "tool_call_id", None)
            tool_info = {
                "tool": part.tool_name,
                "args": tool_args,
                "timestamp": getattr(part, "timestamp", None),
                "tool_call_id": tool_call_id,
            }
            state_manager.session.tool_calls.append(tool_info)

    # After tools are processed, transition back to RESPONSE
    if (
        is_processing_tools
        and response_state
        and response_state.can_transition_to(AgentState.RESPONSE)
    ):
        response_state.transition_to(AgentState.RESPONSE)

    # Update has_user_response based on presence of actual response content
    if (
        response_state
        and hasattr(node, "result")
        and node.result
        and hasattr(node.result, "output")
        and node.result.output
    ):
        response_state.has_user_response = True
