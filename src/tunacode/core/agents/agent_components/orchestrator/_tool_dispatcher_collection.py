"""Tool call collection helpers for tool_dispatcher."""

from typing import Any

from tunacode.types import ToolArgs

from tunacode.core.logging import get_logger
from tunacode.core.types import StateManagerProtocol

from ._tool_dispatcher_constants import (
    DEBUG_PREVIEW_MAX_LENGTH,
    PART_KIND_TEXT,
    PART_KIND_TOOL_CALL,
    TEXT_PART_JOINER,
    UNKNOWN_TOOL_NAME,
)
from ._tool_dispatcher_names import _is_suspicious_tool_name, _normalize_tool_name
from ._tool_dispatcher_registry import (
    _register_tool_call,
    normalize_tool_args,
    record_tool_call_args,
)


def _ensure_normalized_tool_call_part(part: Any, normalized_tool_name: str) -> Any:
    """Return a tool-call part with a normalized tool name.

    pydantic-ai parts may be frozen, so we create a new ToolCallPart instead of
    mutating in-place.
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


async def _collect_structured_tool_calls(
    parts: list[Any],
    state_manager: StateManagerProtocol,
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
                tool_name_preview=tool_name[:DEBUG_PREVIEW_MAX_LENGTH] if tool_name else None,
                tool_name_len=len(tool_name) if tool_name else 0,
                raw_args_preview=str(getattr(part, "args", {}))[:DEBUG_PREVIEW_MAX_LENGTH],
            )
        elif debug_mode:
            logger.debug(
                f"[TOOL_DISPATCH] Native tool call: {tool_name}",
                args_keys=list(tool_args.keys()) if tool_args else [],
            )

    return records


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
                text_preview=text_content[:DEBUG_PREVIEW_MAX_LENGTH],
            )
        return []

    if debug_mode:
        result_with_diagnostics = parse_tool_calls_from_text(
            text_content,
            collect_diagnostics=True,
        )
        if not isinstance(result_with_diagnostics, tuple) or len(result_with_diagnostics) != 2:
            raise RuntimeError(
                "Fallback parser contract violated: expected "
                "(parsed_calls, diagnostics) tuple from "
                "parse_tool_calls_from_text(..., collect_diagnostics=True). "
                f"got {type(result_with_diagnostics).__name__}"
            )
        parsed_calls, diagnostics = result_with_diagnostics
        if not isinstance(parsed_calls, list):
            raise RuntimeError(
                "Fallback parser contract violated: expected list of parsed calls; "
                f"got {type(parsed_calls).__name__}"
            )
        logger.debug(diagnostics.format_for_debug())
    else:
        parsed_calls = parse_tool_calls_from_text(text_content)
        if not isinstance(parsed_calls, list):
            raise RuntimeError(
                "Fallback parser contract violated: expected list from "
                "parse_tool_calls_from_text(..., collect_diagnostics=False). "
                f"got {type(parsed_calls).__name__}"
            )

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
