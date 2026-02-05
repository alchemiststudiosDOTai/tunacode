"""Tool call collection, registration, and execution.

Responsibilities:
  1. Collect tool calls from response parts (structured or fallback)
  2. Register/normalize them in the tool registry
  3. Execute them in parallel with failure tracking

Does NOT own state transitions — the orchestrator drives those.
"""

import time
from dataclasses import dataclass
from typing import Any

from tunacode.constants import (
    ERROR_TOOL_ARGS_MISSING,
    ERROR_TOOL_CALL_ID_MISSING,
)
from tunacode.exceptions import StateError, UserAbortError
from tunacode.types import ToolArgs, ToolCallId
from tunacode.types.callbacks import ToolCallback, ToolStartCallback

from tunacode.core.logging import get_logger
from tunacode.core.types import StateManagerProtocol

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PART_KIND_TEXT = "text"
PART_KIND_TOOL_CALL = "tool-call"
UNKNOWN_TOOL_NAME = "unknown"

TEXT_PART_JOINER = "\n"
TOOL_NAME_JOINER = ", "
TOOL_NAME_SUFFIX = "..."

TOOL_BATCH_PREVIEW_COUNT = 3
TOOL_NAMES_DISPLAY_LIMIT = 5

INVALID_TOOL_NAME_CHARS = frozenset("<>(){}[]\"'`")
MAX_TOOL_NAME_LENGTH = 50

TOOL_FAILURE_TEMPLATE = "{error_type}: {error_message}"

# ---------------------------------------------------------------------------
# Tool name helpers
# ---------------------------------------------------------------------------


def _is_suspicious_tool_name(tool_name: str) -> bool:
    """Check if a tool name looks malformed (contains special chars)."""
    if not tool_name:
        return True
    if len(tool_name) > MAX_TOOL_NAME_LENGTH:
        return True
    return any(c in INVALID_TOOL_NAME_CHARS for c in tool_name)


def _normalize_tool_name(raw_tool_name: str | None) -> str:
    """Normalize tool names to avoid dispatch errors from whitespace."""
    if raw_tool_name is None:
        return UNKNOWN_TOOL_NAME
    normalized = raw_tool_name.strip()
    return normalized if normalized else UNKNOWN_TOOL_NAME


# ---------------------------------------------------------------------------
# Tool registry lifecycle
# ---------------------------------------------------------------------------


def _register_tool_call(
    state_manager: StateManagerProtocol,
    tool_call_id: ToolCallId | None,
    tool_name: str,
    tool_args: ToolArgs,
) -> None:
    """Register a tool call in the runtime registry."""
    if not tool_call_id:
        return
    state_manager.session.runtime.tool_registry.register(tool_call_id, tool_name, tool_args)


def _mark_tool_calls_running(
    state_manager: StateManagerProtocol,
    tasks: list[tuple[Any, Any]],
) -> None:
    """Mark tool calls as running for upcoming tasks."""
    registry = state_manager.session.runtime.tool_registry
    for part, _ in tasks:
        tool_call_id = getattr(part, "tool_call_id", None)
        if tool_call_id:
            registry.start(tool_call_id)


def _record_tool_failure(
    state_manager: StateManagerProtocol,
    part: Any,
    error: BaseException,
) -> None:
    """Record a failed tool call in the registry."""
    tool_call_id = getattr(part, "tool_call_id", None)
    if not tool_call_id:
        return

    registry = state_manager.session.runtime.tool_registry
    if isinstance(error, UserAbortError):
        registry.cancel(tool_call_id, reason=str(error))
        return

    error_message = str(error)
    error_type = type(error).__name__
    error_detail = (
        TOOL_FAILURE_TEMPLATE.format(error_type=error_type, error_message=error_message)
        if error_message
        else error_type
    )
    registry.fail(tool_call_id, error_detail)


# ---------------------------------------------------------------------------
# Arg normalization and storage
# ---------------------------------------------------------------------------


async def normalize_tool_args(raw_args: Any) -> ToolArgs:
    """Parse raw tool args into a normalized structure."""
    from tunacode.tools.parsing.command_parser import parse_args

    return await parse_args(raw_args)


async def record_tool_call_args(
    part: Any,
    state_manager: StateManagerProtocol,
    *,
    normalized_tool_name: str | None = None,
) -> ToolArgs:
    """Parse tool args and register the tool call.

    Notes:
        pydantic-ai message parts may be frozen. Avoid mutating `part` in-place.
        Instead, normalize the tool name for registry bookkeeping and let the
        dispatcher construct a normalized execution part when needed.
    """
    raw_args = getattr(part, "args", {})
    parsed_args = await normalize_tool_args(raw_args)

    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    raw_tool_name = getattr(part, "tool_name", None)
    tool_name = normalized_tool_name or _normalize_tool_name(raw_tool_name)

    _register_tool_call(state_manager, tool_call_id, tool_name, parsed_args)
    return parsed_args


def consume_tool_call_args(part: Any, state_manager: StateManagerProtocol) -> ToolArgs:
    """Retrieve stored tool args for a tool return part."""
    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    if not tool_call_id:
        raise StateError(ERROR_TOOL_CALL_ID_MISSING)
    tool_call_args = state_manager.session.runtime.tool_registry.get_args(tool_call_id)
    if tool_call_args is None:
        raise StateError(ERROR_TOOL_ARGS_MISSING.format(tool_call_id=tool_call_id))
    return tool_call_args


def has_tool_calls(parts: list[Any]) -> bool:
    """Check for structured tool call parts."""
    return any(getattr(part, "part_kind", None) == PART_KIND_TOOL_CALL for part in parts)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolDispatchResult:
    """Summary of tool dispatch work."""

    has_tool_calls: bool
    used_fallback: bool


# ---------------------------------------------------------------------------
# Tool call part normalization
# ---------------------------------------------------------------------------


def _ensure_normalized_tool_call_part(part: Any, normalized_tool_name: str) -> Any:
    """Return a tool-call part whose tool_name matches `normalized_tool_name`.

    pydantic-ai parts may be frozen, so when normalization is required we
    construct a new ToolCallPart for execution instead of mutating in-place.
    """
    raw_tool_name = getattr(part, "tool_name", None)
    if raw_tool_name == normalized_tool_name:
        return part

    tool_call_id = getattr(part, "tool_call_id", None)
    if tool_call_id is None:
        return part

    from pydantic_ai.messages import ToolCallPart

    return ToolCallPart(
        tool_name=normalized_tool_name,
        args=getattr(part, "args", {}),
        tool_call_id=tool_call_id,
    )


# ---------------------------------------------------------------------------
# Collection: structured tool calls
# ---------------------------------------------------------------------------


async def _collect_structured_tool_calls(
    parts: list[Any],
    node: Any,
    state_manager: StateManagerProtocol,
    tool_callback: ToolCallback | None,
) -> list[tuple[Any, ToolArgs]]:
    """Collect structured tool-call parts, register them, return (part, args) pairs."""
    logger = get_logger()
    debug_mode = getattr(state_manager.session, "debug_mode", False)
    records: list[tuple[Any, ToolArgs]] = []

    for part in parts:
        if getattr(part, "part_kind", None) != PART_KIND_TOOL_CALL:
            continue

        raw_tool_name = getattr(part, "tool_name", None)
        normalized_tool_name = _normalize_tool_name(raw_tool_name)

        tool_args = await record_tool_call_args(
            part,
            state_manager,
            normalized_tool_name=normalized_tool_name,
        )
        execution_part = _ensure_normalized_tool_call_part(part, normalized_tool_name)
        records.append((execution_part, tool_args))

        if debug_mode and raw_tool_name != normalized_tool_name:
            logger.debug(
                "[TOOL_DISPATCH] Normalized tool name",
                raw_tool_name=raw_tool_name,
                normalized_tool_name=normalized_tool_name,
            )

        tool_name = getattr(execution_part, "tool_name", UNKNOWN_TOOL_NAME)
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

    return records


# ---------------------------------------------------------------------------
# Collection: fallback text parsing
# ---------------------------------------------------------------------------


async def _collect_fallback_tool_calls(
    parts: list[Any],
    state_manager: StateManagerProtocol,
) -> list[tuple[Any, ToolArgs]]:
    """Extract tool calls from text parts using fallback parsing."""
    from pydantic_ai.messages import ToolCallPart

    from tunacode.tools.parsing.tool_parser import (
        has_potential_tool_call,
        parse_tool_calls_from_text,
    )

    logger = get_logger()
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
    debug_mode = getattr(state_manager.session, "debug_mode", False)

    if not has_potential_tool_call(text_content):
        if debug_mode:
            logger.debug(
                "Fallback parse skipped: no tool call indicators",
                text_preview=text_content[:100],
            )
        return []

    # Parse with diagnostics when debug mode is on
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

    records: list[tuple[Any, ToolArgs]] = []
    for parsed in parsed_calls:
        normalized_tool_name = _normalize_tool_name(parsed.tool_name)
        part = ToolCallPart(
            tool_name=normalized_tool_name,
            args=parsed.args,
            tool_call_id=parsed.tool_call_id,
        )
        tool_args = await normalize_tool_args(parsed.args)
        _register_tool_call(state_manager, parsed.tool_call_id, normalized_tool_name, tool_args)
        records.append((part, tool_args))

    return records


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


async def _execute_tool_batch(
    records: list[tuple[Any, ToolArgs]],
    node: Any,
    state_manager: StateManagerProtocol,
    tool_callback: ToolCallback,
    tool_start_callback: ToolStartCallback | None,
) -> None:
    """Mark tools running, notify start callback, execute in parallel."""
    from ..tool_executor import execute_tools_parallel

    tasks = [(part, node) for part, _args in records]
    _mark_tool_calls_running(state_manager, tasks)

    runtime = state_manager.session.runtime
    runtime.batch_counter += 1

    if tool_start_callback:
        preview_names = [
            getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
            for part, _ in tasks[:TOOL_BATCH_PREVIEW_COUNT]
        ]
        suffix = TOOL_NAME_SUFFIX if len(tasks) > TOOL_BATCH_PREVIEW_COUNT else ""
        tool_start_callback(TOOL_NAME_JOINER.join(preview_names) + suffix)

    def tool_failure_callback(part: Any, error: BaseException) -> None:
        _record_tool_failure(state_manager, part, error)

    await execute_tools_parallel(
        tasks,
        tool_callback,
        tool_failure_callback=tool_failure_callback,
    )


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _log_dispatch_summary(
    records: list[tuple[Any, ToolArgs]],
    elapsed_ms: float,
) -> None:
    """Log a summary of dispatched tool calls."""
    logger = get_logger()
    total = len(records)

    if not total:
        logger.lifecycle("No tool calls this iteration")
        return

    names = [getattr(part, "tool_name", UNKNOWN_TOOL_NAME) for part, _ in records]
    names_str = ", ".join(names[:TOOL_NAMES_DISPLAY_LIMIT])
    if len(names) > TOOL_NAMES_DISPLAY_LIMIT:
        names_str += f" (+{len(names) - TOOL_NAMES_DISPLAY_LIMIT} more)"

    logger.lifecycle(f"Tools: [{names_str}] ({total} total, {elapsed_ms:.0f}ms)")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def dispatch_tools(
    parts: list[Any],
    node: Any,
    state_manager: StateManagerProtocol,
    tool_callback: ToolCallback | None,
    tool_start_callback: ToolStartCallback | None,
    response_state_transition: Any | None = None,
) -> ToolDispatchResult:
    """Collect, register, and execute tool calls from response parts.

    Args:
        parts: Model response parts to scan for tool calls.
        node: The agent response node (passed to tool executor).
        state_manager: Session state for registry access.
        tool_callback: Callback to execute tools. None = record-only mode.
        tool_start_callback: UI notification when tool batch starts.
        response_state_transition: Callable to transition state to TOOL_EXECUTION.
            Injected by orchestrator to keep state machine ownership there.

    Returns:
        ToolDispatchResult summarizing what happened.
    """
    logger = get_logger()
    dispatch_start = time.perf_counter()
    used_fallback = False

    # Phase 1: Collect structured tool calls
    records = await _collect_structured_tool_calls(parts, node, state_manager, tool_callback)

    # Phase 2: Fallback to text parsing if no structured calls found
    if not records and tool_callback:
        fallback_records = await _collect_fallback_tool_calls(parts, state_manager)
        if fallback_records:
            used_fallback = True
            records = fallback_records
            logger.lifecycle(f"Fallback tool parsing used (count={len(records)})")

    has_tools = bool(records)

    # Notify orchestrator that tools were found (for state transition)
    if has_tools and response_state_transition:
        response_state_transition()

    # Phase 3: Execute if we have a callback
    if records and tool_callback:
        await _execute_tool_batch(records, node, state_manager, tool_callback, tool_start_callback)

    # Phase 4: Log summary
    elapsed_ms = (time.perf_counter() - dispatch_start) * 1000
    _log_dispatch_summary(records, elapsed_ms)

    return ToolDispatchResult(has_tool_calls=has_tools, used_fallback=used_fallback)
