"""Tool categorization and execution for agent responses."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from tunacode.constants import ERROR_TOOL_ARGS_MISSING, ERROR_TOOL_CALL_ID_MISSING, READ_ONLY_TOOLS
from tunacode.core.logging import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import StateError, UserAbortError
from tunacode.types import AgentState, ToolArgs, ToolCallId
from tunacode.types.callbacks import ToolCallback, ToolStartCallback

from ..response_state import ResponseState

PART_KIND_TEXT = "text"
PART_KIND_TOOL_CALL = "tool-call"
RESEARCH_TOOL_NAME = "research_codebase"
UNKNOWN_TOOL_NAME = "unknown"
TOOL_BATCH_PREVIEW_COUNT = 3
TEXT_PART_JOINER = "\n"
TOOL_NAME_JOINER = ", "
TOOL_NAME_SUFFIX = "..."

TOOL_START_RESEARCH_LABEL = "research"


@dataclass(frozen=True, slots=True)
class ToolDispatchResult:
    """Summary of tool dispatch work."""

    has_tool_calls: bool
    used_fallback: bool


async def normalize_tool_args(raw_args: Any) -> ToolArgs:
    """Parse raw tool args into a normalized structure."""
    from tunacode.utils.parsing.command_parser import parse_args

    parsed_args = await parse_args(raw_args)
    return cast(ToolArgs, parsed_args)


async def record_tool_call_args(part: Any, state_manager: StateManager) -> ToolArgs:
    """Parse and store tool args keyed by tool_call_id."""
    raw_args = getattr(part, "args", {})
    parsed_args = await normalize_tool_args(raw_args)
    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    if tool_call_id:
        state_manager.session.tool_call_args_by_id[tool_call_id] = parsed_args
    return parsed_args


def consume_tool_call_args(part: Any, state_manager: StateManager) -> ToolArgs:
    """Consume stored tool args for a tool return part."""
    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    if not tool_call_id:
        raise StateError(ERROR_TOOL_CALL_ID_MISSING)
    tool_call_args = state_manager.session.tool_call_args_by_id.pop(tool_call_id, None)
    if tool_call_args is None:
        raise StateError(ERROR_TOOL_ARGS_MISSING.format(tool_call_id=tool_call_id))
    return tool_call_args


def has_tool_calls(parts: list[Any]) -> bool:
    """Check for structured tool call parts."""
    return any(getattr(part, "part_kind", None) == PART_KIND_TOOL_CALL for part in parts)


async def _extract_fallback_tool_calls(
    parts: list[Any],
    state_manager: StateManager,
    response_state: ResponseState | None,
) -> list[tuple[Any, ToolArgs]]:
    """Extract tool calls from text parts using fallback parsing."""
    from pydantic_ai.messages import ToolCallPart

    from tunacode.utils.parsing.tool_parser import (
        has_potential_tool_call,
        parse_tool_calls_from_text,
    )

    text_segments: list[str] = []
    for part in parts:
        part_kind = getattr(part, "part_kind", None)
        if part_kind != PART_KIND_TEXT:
            continue
        content = getattr(part, "content", "")
        if content:
            text_segments.append(content)

    if not text_segments:
        return []

    text_content = TEXT_PART_JOINER.join(text_segments)
    if not has_potential_tool_call(text_content):
        return []

    parsed_calls = parse_tool_calls_from_text(text_content)
    if not parsed_calls:
        return []

    if response_state and response_state.can_transition_to(AgentState.TOOL_EXECUTION):
        response_state.transition_to(AgentState.TOOL_EXECUTION)

    results: list[tuple[Any, ToolArgs]] = []
    for parsed in parsed_calls:
        part = ToolCallPart(
            tool_name=parsed.tool_name,
            args=parsed.args,
            tool_call_id=parsed.tool_call_id,
        )
        tool_args = await normalize_tool_args(parsed.args)
        state_manager.session.tool_call_args_by_id[parsed.tool_call_id] = tool_args
        results.append((part, tool_args))

    return results


ToolResultCallback = Callable[..., None]


async def dispatch_tools(
    parts: list[Any],
    node: Any,
    state_manager: StateManager,
    tool_callback: ToolCallback | None,
    _tool_result_callback: ToolResultCallback | None,
    tool_start_callback: ToolStartCallback | None,
    response_state: ResponseState | None,
) -> ToolDispatchResult:
    """Categorize, batch, and execute tool calls from response parts."""
    from ..tool_executor import execute_tools_parallel

    logger = get_logger()

    is_processing_tools = False
    used_fallback = False

    read_only_tasks: list[tuple[Any, Any]] = []
    research_agent_tasks: list[tuple[Any, Any]] = []
    write_execute_tasks: list[tuple[Any, Any]] = []
    tool_call_records: list[tuple[Any, ToolArgs]] = []

    for part in parts:
        part_kind = getattr(part, "part_kind", None)
        if part_kind != PART_KIND_TOOL_CALL:
            continue

        is_processing_tools = True
        if response_state and response_state.can_transition_to(AgentState.TOOL_EXECUTION):
            response_state.transition_to(AgentState.TOOL_EXECUTION)

        tool_args = await record_tool_call_args(part, state_manager)
        tool_call_records.append((part, tool_args))

        if not tool_callback:
            continue

        tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
        if tool_name == RESEARCH_TOOL_NAME:
            research_agent_tasks.append((part, node))
        elif tool_name in READ_ONLY_TOOLS:
            read_only_tasks.append((part, node))
        else:
            write_execute_tasks.append((part, node))

    if not tool_call_records and tool_callback:
        fallback_tool_calls = await _extract_fallback_tool_calls(
            parts,
            state_manager,
            response_state,
        )

        if fallback_tool_calls:
            used_fallback = True
            is_processing_tools = True
            for part, tool_args in fallback_tool_calls:
                tool_call_records.append((part, tool_args))
                tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
                if tool_name == RESEARCH_TOOL_NAME:
                    research_agent_tasks.append((part, node))
                elif tool_name in READ_ONLY_TOOLS:
                    read_only_tasks.append((part, node))
                else:
                    write_execute_tasks.append((part, node))

    if research_agent_tasks and tool_callback:
        logger.debug(f"Phase 2: research agent ({len(research_agent_tasks)} calls)")

        if tool_start_callback:
            tool_start_callback(TOOL_START_RESEARCH_LABEL)

        await execute_tools_parallel(research_agent_tasks, tool_callback)

    if read_only_tasks and tool_callback:
        logger.debug(f"Phase 3: read-only batch ({len(read_only_tasks)} calls)")

        batch_id = state_manager.session.batch_counter + 1
        state_manager.session.batch_counter = batch_id

        if tool_start_callback:
            preview_tasks = read_only_tasks[:TOOL_BATCH_PREVIEW_COUNT]
            preview_names = [
                getattr(part, "tool_name", UNKNOWN_TOOL_NAME) for part, _ in preview_tasks
            ]
            suffix = TOOL_NAME_SUFFIX if len(read_only_tasks) > TOOL_BATCH_PREVIEW_COUNT else ""
            tool_start_callback(TOOL_NAME_JOINER.join(preview_names) + suffix)

        await execute_tools_parallel(read_only_tasks, tool_callback)

    if write_execute_tasks:
        logger.debug(f"Phase 4: write/execute ({len(write_execute_tasks)} calls)")

    for part, task_node in write_execute_tasks:
        if tool_start_callback:
            tool_start_callback(getattr(part, "tool_name", UNKNOWN_TOOL_NAME))

        try:
            await tool_callback(part, task_node)
        except UserAbortError:
            raise

    if tool_call_records:
        session_tool_calls = state_manager.session.tool_calls
        for part, tool_args in tool_call_records:
            tool_call_id = getattr(part, "tool_call_id", None)
            tool_info = {
                "tool": getattr(part, "tool_name", UNKNOWN_TOOL_NAME),
                "args": tool_args,
                "timestamp": getattr(part, "timestamp", None),
                "tool_call_id": tool_call_id,
            }
            session_tool_calls.append(tool_info)

    if (
        is_processing_tools
        and response_state
        and response_state.can_transition_to(AgentState.RESPONSE)
    ):
        response_state.transition_to(AgentState.RESPONSE)

    if response_state:
        result = getattr(node, "result", None)
        result_output = getattr(result, "output", None)
        if result_output:
            response_state.has_user_response = True

    return ToolDispatchResult(
        has_tool_calls=is_processing_tools,
        used_fallback=used_fallback,
    )
