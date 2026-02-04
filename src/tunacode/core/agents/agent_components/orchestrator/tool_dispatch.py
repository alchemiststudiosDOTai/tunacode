"""Tool dispatch - coordinates tool execution from response parts.

This module is responsible for:
1. Identifying tool calls in response parts
2. Coordinating parallel tool execution
3. Handling fallback parsing when structured calls are missing
"""

import time
from dataclasses import dataclass
from typing import Any

from tunacode.types import ToolArgs
from tunacode.types.callbacks import ToolCallback, ToolResultCallback, ToolStartCallback

from tunacode.core.logging import get_logger
from tunacode.core.types import StateManagerProtocol

from ..response_state import ResponseState
from . import state_ops
from .tool_registry_ops import (
    is_suspicious_tool_name,
    mark_tools_running,
    normalize_tool_name,
    parse_and_register_args,
    record_tool_failure,
    register_tool_call,
)

PART_KIND_TEXT = "text"
PART_KIND_TOOL_CALL = "tool-call"
UNKNOWN_TOOL_NAME = "unknown"
TEXT_PART_JOINER = "\n"

# Display limits
TOOL_BATCH_PREVIEW_COUNT = 3
TOOL_NAMES_DISPLAY_LIMIT = 5
TOOL_NAME_JOINER = ", "
TOOL_NAME_SUFFIX = "..."


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """Result of tool dispatch operation."""

    has_tool_calls: bool
    used_fallback: bool
    tool_count: int


def has_tool_calls(parts: list[Any]) -> bool:
    """Check for structured tool call parts."""
    return any(getattr(part, "part_kind", None) == PART_KIND_TOOL_CALL for part in parts)


async def _extract_native_tool_calls(
    parts: list[Any],
    state_manager: StateManagerProtocol,
    response_state: ResponseState | None,
    debug_mode: bool,
) -> list[tuple[Any, ToolArgs]]:
    """Extract tool calls from native structured parts."""
    logger = get_logger()
    tool_records: list[tuple[Any, ToolArgs]] = []

    for part in parts:
        part_kind = getattr(part, "part_kind", None)
        if part_kind != PART_KIND_TOOL_CALL:
            continue

        # First tool call triggers state transition
        if not tool_records:
            state_ops.transition_to_tool_execution(response_state)

        tool_args = await parse_and_register_args(part, state_manager)
        tool_records.append((part, tool_args))

        tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)

        if debug_mode:
            if is_suspicious_tool_name(tool_name):
                logger.debug(
                    "[TOOL_DISPATCH] SUSPICIOUS tool_name detected",
                    tool_name_preview=tool_name[:100] if tool_name else None,
                    tool_name_len=len(tool_name) if tool_name else 0,
                    raw_args_preview=str(getattr(part, "args", {}))[:100],
                )
            else:
                logger.debug(
                    f"[TOOL_DISPATCH] Native tool call: {tool_name}",
                    args_keys=list(tool_args.keys()) if tool_args else [],
                )

    return tool_records


async def _extract_fallback_tool_calls(
    parts: list[Any],
    state_manager: StateManagerProtocol,
    response_state: ResponseState | None,
    debug_mode: bool,
) -> list[tuple[Any, ToolArgs]]:
    """Extract tool calls from text parts using fallback parsing."""
    from pydantic_ai.messages import ToolCallPart

    from tunacode.tools.parsing.command_parser import parse_args
    from tunacode.tools.parsing.tool_parser import (
        has_potential_tool_call,
        parse_tool_calls_from_text,
    )

    logger = get_logger()

    # Collect text segments
    text_segments: list[str] = []
    for part in parts:
        if getattr(part, "part_kind", None) != PART_KIND_TEXT:
            continue
        content = getattr(part, "content", "")
        if content:
            text_segments.append(content)

    if not text_segments:
        return []

    text_content = TEXT_PART_JOINER.join(text_segments)

    if not has_potential_tool_call(text_content):
        if debug_mode:
            logger.debug(
                "Fallback parse skipped: no tool call indicators",
                text_preview=text_content[:100],
            )
        return []

    # Parse with optional diagnostics
    if debug_mode:
        result = parse_tool_calls_from_text(text_content, collect_diagnostics=True)
        assert isinstance(result, tuple), "Expected tuple with diagnostics"
        parsed_calls, diagnostics = result
        logger.debug(diagnostics.format_for_debug())
    else:
        result = parse_tool_calls_from_text(text_content)
        assert isinstance(result, list), "Expected list without diagnostics"
        parsed_calls = result

    if not parsed_calls:
        if debug_mode:
            logger.debug(
                "Fallback parse: indicators found but no valid tool calls extracted",
                text_len=len(text_content),
            )
        return []

    state_ops.transition_to_tool_execution(response_state)

    # Convert parsed calls to tool records
    results: list[tuple[Any, ToolArgs]] = []
    for parsed in parsed_calls:
        normalized_name = normalize_tool_name(parsed.tool_name)
        part = ToolCallPart(
            tool_name=normalized_name,
            args=parsed.args,
            tool_call_id=parsed.tool_call_id,
        )
        tool_args = await parse_args(parsed.args)
        register_tool_call(state_manager, parsed.tool_call_id, normalized_name, tool_args)
        results.append((part, tool_args))

    return results


def _format_tool_names_for_log(tool_records: list[tuple[Any, ToolArgs]]) -> str:
    """Format tool names for lifecycle logging."""
    tool_names = [getattr(part, "tool_name", UNKNOWN_TOOL_NAME) for part, _ in tool_records]
    names_str = TOOL_NAME_JOINER.join(tool_names[:TOOL_NAMES_DISPLAY_LIMIT])
    if len(tool_names) > TOOL_NAMES_DISPLAY_LIMIT:
        names_str += f" (+{len(tool_names) - TOOL_NAMES_DISPLAY_LIMIT} more)"
    return names_str


async def dispatch_tools(
    parts: list[Any],
    node: Any,
    state_manager: StateManagerProtocol,
    tool_callback: ToolCallback | None,
    _tool_result_callback: ToolResultCallback | None,
    tool_start_callback: ToolStartCallback | None,
    response_state: ResponseState | None,
) -> DispatchResult:
    """Dispatch tool execution for response parts.

    Coordinates the full tool dispatch flow:
    1. Extract tool calls (native or fallback)
    2. Register and mark tools as running
    3. Execute tools in parallel
    4. Handle state transitions
    """
    from ..tool_executor import execute_tools_parallel

    logger = get_logger()
    session = state_manager.session
    runtime = session.runtime
    debug_mode = getattr(session, "debug_mode", False)

    dispatch_start = time.perf_counter()
    used_fallback = False

    # Try native extraction first
    tool_records = await _extract_native_tool_calls(
        parts, state_manager, response_state, debug_mode
    )

    # Fallback to text parsing if no native calls and callback exists
    if not tool_records and tool_callback:
        tool_records = await _extract_fallback_tool_calls(
            parts, state_manager, response_state, debug_mode
        )
        if tool_records:
            used_fallback = True
            logger.lifecycle(f"Fallback tool parsing used (count={len(tool_records)})")

    # Build task list for execution
    tool_tasks = [(part, node) for part, _ in tool_records] if tool_callback else []

    # Execute tools if we have any
    if tool_tasks and tool_callback:
        mark_tools_running(state_manager, tool_tasks)

        # Update batch counter
        batch_id = runtime.batch_counter + 1
        runtime.batch_counter = batch_id

        # Notify tool start
        if tool_start_callback:
            preview_tasks = tool_tasks[:TOOL_BATCH_PREVIEW_COUNT]
            preview_names = [
                getattr(part, "tool_name", UNKNOWN_TOOL_NAME) for part, _ in preview_tasks
            ]
            suffix = TOOL_NAME_SUFFIX if len(tool_tasks) > TOOL_BATCH_PREVIEW_COUNT else ""
            tool_start_callback(TOOL_NAME_JOINER.join(preview_names) + suffix)

        def failure_callback(part: Any, error: BaseException) -> None:
            record_tool_failure(state_manager, part, error)

        await execute_tools_parallel(
            tool_tasks,
            tool_callback,
            tool_failure_callback=failure_callback,
        )

    # Transition to response state after tool execution
    if tool_records:
        state_ops.transition_to_response(response_state)

    # Check for user response output
    if response_state:
        result_output = getattr(getattr(node, "result", None), "output", None)
        state_ops.mark_has_user_response(response_state, bool(result_output))

    # Log dispatch summary
    dispatch_elapsed_ms = (time.perf_counter() - dispatch_start) * 1000
    total_tools = len(tool_records)

    if total_tools:
        tool_names_str = _format_tool_names_for_log(tool_records)
        elapsed_ms = f"{dispatch_elapsed_ms:.0f}ms"
        logger.lifecycle(f"Tools: [{tool_names_str}] ({total_tools} total, {elapsed_ms})")
    else:
        logger.lifecycle("No tool calls this iteration")

    return DispatchResult(
        has_tool_calls=bool(tool_records),
        used_fallback=used_fallback,
        tool_count=total_tools,
    )
