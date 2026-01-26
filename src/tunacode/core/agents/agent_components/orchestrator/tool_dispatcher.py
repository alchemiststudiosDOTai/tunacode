"""Tool categorization and execution for agent responses."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tunacode.constants import (
    ERROR_TOOL_ARGS_MISSING,
    ERROR_TOOL_CALL_ID_MISSING,
    READ_ONLY_TOOLS,
)
from tunacode.exceptions import StateError, UserAbortError
from tunacode.types import AgentState, ToolArgs, ToolCallId
from tunacode.types.callbacks import ToolCallback, ToolStartCallback

from tunacode.core.logging import get_logger
from tunacode.core.state import StateManager

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

# Maximum tool names to display in lifecycle logs before truncating
TOOL_NAMES_DISPLAY_LIMIT = 5

# Characters that should never appear in valid tool names
INVALID_TOOL_NAME_CHARS = frozenset("<>(){}[]\"'`")

TOOL_FAILURE_TEMPLATE = "{error_type}: {error_message}"


def _is_suspicious_tool_name(tool_name: str) -> bool:
    """Check if a tool name looks malformed (contains special chars)."""
    if not tool_name:
        return True
    if len(tool_name) > 50:  # Tool names shouldn't be this long
        return True
    return any(c in INVALID_TOOL_NAME_CHARS for c in tool_name)


def _register_tool_call(
    state_manager: StateManager,
    tool_call_id: ToolCallId | None,
    tool_name: str,
    tool_args: ToolArgs,
) -> None:
    """Register a tool call in the runtime registry."""
    if not tool_call_id:
        return
    tool_registry = state_manager.session.runtime.tool_registry
    tool_registry.register(tool_call_id, tool_name, tool_args)


def _mark_tool_calls_running(
    state_manager: StateManager,
    tasks: list[tuple[Any, Any]],
) -> None:
    """Mark tool calls as running for upcoming tasks."""
    tool_registry = state_manager.session.runtime.tool_registry
    for part, _ in tasks:
        tool_call_id = getattr(part, "tool_call_id", None)
        if not tool_call_id:
            continue
        tool_registry.start(tool_call_id)


def _record_tool_failure(
    state_manager: StateManager,
    part: Any,
    error: Exception,
) -> None:
    """Record a failed tool call in the registry."""
    tool_call_id = getattr(part, "tool_call_id", None)
    if not tool_call_id:
        return

    tool_registry = state_manager.session.runtime.tool_registry
    if isinstance(error, UserAbortError):
        tool_registry.cancel(tool_call_id, reason=str(error))
        return

    error_message = str(error)
    error_type = type(error).__name__
    error_detail = (
        TOOL_FAILURE_TEMPLATE.format(error_type=error_type, error_message=error_message)
        if error_message
        else error_type
    )
    tool_registry.fail(tool_call_id, error_detail)


@dataclass(frozen=True, slots=True)
class ToolDispatchResult:
    """Summary of tool dispatch work."""

    has_tool_calls: bool
    used_fallback: bool


async def normalize_tool_args(raw_args: Any) -> ToolArgs:
    """Parse raw tool args into a normalized structure."""
    from tunacode.utils.parsing.command_parser import parse_args

    parsed_args = await parse_args(raw_args)
    return parsed_args


async def record_tool_call_args(part: Any, state_manager: StateManager) -> ToolArgs:
    """Parse tool args and register the tool call."""
    raw_args = getattr(part, "args", {})
    parsed_args = await normalize_tool_args(raw_args)
    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
    _register_tool_call(state_manager, tool_call_id, tool_name, parsed_args)
    return parsed_args


def consume_tool_call_args(part: Any, state_manager: StateManager) -> ToolArgs:
    """Retrieve stored tool args for a tool return part."""
    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    if not tool_call_id:
        raise StateError(ERROR_TOOL_CALL_ID_MISSING)
    tool_registry = state_manager.session.runtime.tool_registry
    tool_call_args = tool_registry.get_args(tool_call_id)
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

    logger = get_logger()
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
    has_potential = has_potential_tool_call(text_content)

    # Always collect diagnostics when debug_mode is enabled
    debug_mode = getattr(state_manager.session, "debug_mode", False)

    if not has_potential:
        if debug_mode:
            logger.debug(
                "Fallback parse skipped: no tool call indicators",
                text_preview=text_content[:100],
            )
        return []

    # Parse with diagnostics when debug mode is on
    if debug_mode:
        result = parse_tool_calls_from_text(text_content, collect_diagnostics=True)
        # When collect_diagnostics=True, return is (list, ParseDiagnostics)
        assert isinstance(result, tuple), "Expected tuple with diagnostics"
        parsed_calls, diagnostics = result
        # Log the diagnostics
        logger.debug(diagnostics.format_for_debug())
    else:
        result = parse_tool_calls_from_text(text_content)
        # When collect_diagnostics=False, return is list[ParsedToolCall]
        assert isinstance(result, list), "Expected list without diagnostics"
        parsed_calls = result

    if not parsed_calls:
        if debug_mode:
            logger.debug(
                "Fallback parse: indicators found but no valid tool calls extracted",
                text_len=len(text_content),
            )
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
        _register_tool_call(state_manager, parsed.tool_call_id, parsed.tool_name, tool_args)
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
    session = state_manager.session
    runtime = session.runtime

    is_processing_tools = False
    used_fallback = False

    read_only_tasks: list[tuple[Any, Any]] = []
    research_agent_tasks: list[tuple[Any, Any]] = []
    write_execute_tasks: list[tuple[Any, Any]] = []
    tool_call_records: list[tuple[Any, ToolArgs]] = []

    debug_mode = getattr(session, "debug_mode", False)

    dispatch_start = time.perf_counter()

    for part in parts:
        part_kind = getattr(part, "part_kind", None)
        if part_kind != PART_KIND_TOOL_CALL:
            continue

        is_processing_tools = True
        if response_state and response_state.can_transition_to(AgentState.TOOL_EXECUTION):
            response_state.transition_to(AgentState.TOOL_EXECUTION)

        tool_args = await record_tool_call_args(part, state_manager)
        tool_call_records.append((part, tool_args))

        tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)

        # Log suspicious tool names (likely model format issues)
        if debug_mode and _is_suspicious_tool_name(tool_name):
            logger.debug(
                "[TOOL_DISPATCH] SUSPICIOUS tool_name detected",
                tool_name_preview=tool_name[:100] if tool_name else None,
                tool_name_len=len(tool_name) if tool_name else 0,
                raw_args_preview=str(getattr(part, "args", {}))[:100],
            )
        elif debug_mode:
            logger.debug(
                f"[TOOL_DISPATCH] Native tool call: {tool_name}",
                args_keys=list(tool_args.keys()) if tool_args else [],
            )

        if not tool_callback:
            continue

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
            logger.lifecycle(f"Fallback tool parsing used (count={len(fallback_tool_calls)})")
            for part, tool_args in fallback_tool_calls:
                tool_call_records.append((part, tool_args))
                tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
                if tool_name == RESEARCH_TOOL_NAME:
                    research_agent_tasks.append((part, node))
                elif tool_name in READ_ONLY_TOOLS:
                    read_only_tasks.append((part, node))
                else:
                    write_execute_tasks.append((part, node))

    def tool_failure_callback(part: Any, error: Exception) -> None:
        _record_tool_failure(state_manager, part, error)

    if research_agent_tasks and tool_callback:
        _mark_tool_calls_running(state_manager, research_agent_tasks)
        if tool_start_callback:
            tool_start_callback(TOOL_START_RESEARCH_LABEL)

        await execute_tools_parallel(
            research_agent_tasks,
            tool_callback,
            tool_failure_callback=tool_failure_callback,
        )

    if read_only_tasks and tool_callback:
        _mark_tool_calls_running(state_manager, read_only_tasks)
        batch_id = runtime.batch_counter + 1
        runtime.batch_counter = batch_id

        if tool_start_callback:
            preview_tasks = read_only_tasks[:TOOL_BATCH_PREVIEW_COUNT]
            preview_names = [
                getattr(part, "tool_name", UNKNOWN_TOOL_NAME) for part, _ in preview_tasks
            ]
            suffix = TOOL_NAME_SUFFIX if len(read_only_tasks) > TOOL_BATCH_PREVIEW_COUNT else ""
            tool_start_callback(TOOL_NAME_JOINER.join(preview_names) + suffix)

        await execute_tools_parallel(
            read_only_tasks,
            tool_callback,
            tool_failure_callback=tool_failure_callback,
        )

    if tool_callback is not None:
        for part, task_node in write_execute_tasks:
            if tool_start_callback:
                tool_start_callback(getattr(part, "tool_name", UNKNOWN_TOOL_NAME))

            try:
                _mark_tool_calls_running(state_manager, [(part, task_node)])
                await tool_callback(part, task_node)
            except UserAbortError as error:
                _record_tool_failure(state_manager, part, error)
                raise
            except Exception as error:
                _record_tool_failure(state_manager, part, error)
                raise

    if (
        is_processing_tools
        and response_state
        and response_state.can_transition_to(AgentState.RESPONSE)
    ):
        response_state.transition_to(AgentState.RESPONSE)

    # NOTE: submit tool is just a marker - don't set task_completed here.
    # Let pydantic-ai's loop end naturally after the agent responds.

    if response_state:
        result = getattr(node, "result", None)
        result_output = getattr(result, "output", None)
        if result_output:
            response_state.has_user_response = True

    dispatch_elapsed_ms = (time.perf_counter() - dispatch_start) * 1000
    total_tools = len(tool_call_records)

    if total_tools:
        # Build tool name list for visibility
        tool_names = [
            getattr(part, "tool_name", UNKNOWN_TOOL_NAME) for part, _ in tool_call_records
        ]
        tool_names_str = ", ".join(tool_names[:TOOL_NAMES_DISPLAY_LIMIT])
        if len(tool_names) > TOOL_NAMES_DISPLAY_LIMIT:
            tool_names_str += f" (+{len(tool_names) - TOOL_NAMES_DISPLAY_LIMIT} more)"

        logger.lifecycle(
            f"Tools: [{tool_names_str}] ({total_tools} total, {dispatch_elapsed_ms:.0f}ms)"
        )
    else:
        logger.lifecycle("No tool calls this iteration")

    return ToolDispatchResult(
        has_tool_calls=is_processing_tools,
        used_fallback=used_fallback,
    )
