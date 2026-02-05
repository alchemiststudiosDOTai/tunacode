"""Tool call collection helpers for tool_dispatcher.

This module intentionally keeps the high-branching parsing logic isolated from the
orchestrator-facing dispatcher.
"""

from __future__ import annotations

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


def _safe_preview(value: str | None) -> str | None:
    if not value:
        return None

    return value[:DEBUG_PREVIEW_MAX_LENGTH]


def _safe_len(value: str | None) -> int:
    if not value:
        return 0

    return len(value)


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


def _log_structured_tool_call_debug(
    *,
    logger: Any,
    part: Any,
    tool_args: ToolArgs,
    raw_tool_name: str | None,
    execution_part: Any,
    normalized_tool_name: str,
) -> None:
    if raw_tool_name != normalized_tool_name:
        logger.debug(
            "[TOOL_DISPATCH] Normalized tool name",
            raw_tool_name=raw_tool_name,
            normalized_tool_name=normalized_tool_name,
        )

    tool_name = getattr(execution_part, "tool_name", UNKNOWN_TOOL_NAME)
    if _is_suspicious_tool_name(tool_name):
        logger.debug(
            "[TOOL_DISPATCH] SUSPICIOUS tool_name detected",
            tool_name_preview=_safe_preview(tool_name),
            tool_name_len=_safe_len(tool_name),
            raw_args_preview=_safe_preview(str(getattr(part, "args", {}))),
        )
        return

    logger.debug(
        f"[TOOL_DISPATCH] Native tool call: {tool_name}",
        args_keys=list(tool_args),
    )


async def _collect_structured_tool_call_from_part(
    part: Any,
    state_manager: StateManagerProtocol,
    *,
    debug_mode: bool,
    logger: Any,
) -> tuple[Any, ToolArgs] | None:
    if getattr(part, "part_kind", None) != PART_KIND_TOOL_CALL:
        return None

    raw_tool_name = getattr(part, "tool_name", None)
    normalized_tool_name = _normalize_tool_name(raw_tool_name)

    tool_args = await record_tool_call_args(
        part,
        state_manager,
        normalized_tool_name=normalized_tool_name,
    )
    execution_part = _ensure_normalized_tool_call_part(part, normalized_tool_name)

    if debug_mode:
        _log_structured_tool_call_debug(
            logger=logger,
            part=part,
            tool_args=tool_args,
            raw_tool_name=raw_tool_name,
            execution_part=execution_part,
            normalized_tool_name=normalized_tool_name,
        )

    return (execution_part, tool_args)


async def _collect_structured_tool_calls(
    parts: list[Any],
    state_manager: StateManagerProtocol,
) -> list[tuple[Any, ToolArgs]]:
    """Collect structured tool-call parts, register them, return (part, args) pairs."""

    logger = get_logger()
    debug_mode = getattr(state_manager.session, "debug_mode", False)

    records: list[tuple[Any, ToolArgs]] = []
    for part in parts:
        record = await _collect_structured_tool_call_from_part(
            part,
            state_manager,
            debug_mode=debug_mode,
            logger=logger,
        )
        if record is not None:
            records.append(record)

    return records


def _extract_text_content(parts: list[Any]) -> str:
    text_segments: list[str] = []
    for part in parts:
        if getattr(part, "part_kind", None) != PART_KIND_TEXT:
            continue

        content = getattr(part, "content", "")
        if content:
            text_segments.append(content)

    return TEXT_PART_JOINER.join(text_segments)


def _debug_log_fallback_skipped_no_indicators(
    *,
    logger: Any,
    debug_mode: bool,
    text_content: str,
) -> None:
    if not debug_mode:
        return

    logger.debug(
        "Fallback parse skipped: no tool call indicators",
        text_preview=_safe_preview(text_content) or "",
    )


def _debug_log_fallback_indicators_no_calls(
    *,
    logger: Any,
    debug_mode: bool,
    text_content: str,
) -> None:
    if not debug_mode:
        return

    logger.debug(
        "Fallback parse: indicators found but no valid tool calls extracted",
        text_len=len(text_content),
    )


def _raise_fallback_parser_contract_error(message: str, *, got: Any) -> None:
    raise RuntimeError(f"Fallback parser contract violated: {message}. got {type(got).__name__}")


def _parse_tool_calls_from_text_content(
    *,
    text_content: str,
    debug_mode: bool,
    logger: Any,
) -> list[Any]:
    from tunacode.tools.parsing.tool_parser import parse_tool_calls_from_text

    if not debug_mode:
        parsed_calls = parse_tool_calls_from_text(text_content)
        if not isinstance(parsed_calls, list):
            _raise_fallback_parser_contract_error(
                "expected list from parse_tool_calls_from_text(..., collect_diagnostics=False)",
                got=parsed_calls,
            )
        return parsed_calls

    result_with_diagnostics = parse_tool_calls_from_text(
        text_content,
        collect_diagnostics=True,
    )
    if not isinstance(result_with_diagnostics, tuple) or len(result_with_diagnostics) != 2:
        _raise_fallback_parser_contract_error(
            "expected (parsed_calls, diagnostics) tuple from "
            "parse_tool_calls_from_text(..., collect_diagnostics=True)",
            got=result_with_diagnostics,
        )

    parsed_calls, diagnostics = result_with_diagnostics
    if not isinstance(parsed_calls, list):
        _raise_fallback_parser_contract_error(
            "expected list of parsed calls",
            got=parsed_calls,
        )

    logger.debug(diagnostics.format_for_debug())
    return parsed_calls


async def _register_parsed_tool_calls(
    parsed_calls: list[Any],
    state_manager: StateManagerProtocol,
) -> list[tuple[Any, ToolArgs]]:
    from pydantic_ai.messages import ToolCallPart

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


async def _collect_fallback_tool_calls(
    parts: list[Any],
    state_manager: StateManagerProtocol,
) -> list[tuple[Any, ToolArgs]]:
    """Extract tool calls from text parts using fallback parsing."""

    from tunacode.tools.parsing.tool_parser import has_potential_tool_call

    logger = get_logger()
    debug_mode = getattr(state_manager.session, "debug_mode", False)

    text_content = _extract_text_content(parts)
    if not text_content:
        return []

    if not has_potential_tool_call(text_content):
        _debug_log_fallback_skipped_no_indicators(
            logger=logger,
            debug_mode=debug_mode,
            text_content=text_content,
        )
        return []

    parsed_calls = _parse_tool_calls_from_text_content(
        text_content=text_content,
        debug_mode=debug_mode,
        logger=logger,
    )
    if not parsed_calls:
        _debug_log_fallback_indicators_no_calls(
            logger=logger,
            debug_mode=debug_mode,
            text_content=text_content,
        )
        return []

    return await _register_parsed_tool_calls(parsed_calls, state_manager)
