"""Debug logging helpers for message history sanitization.

Provides formatted debug output for tracing message cleanup operations.
"""

from __future__ import annotations

from typing import Any

from tunacode.types import ToolCallId
from tunacode.utils.messaging import (
    _get_attr,
    _get_parts,
    get_tool_call_ids,
    get_tool_return_ids,
)

from tunacode.core.agents.debug_utils import format_debug_preview, format_part_debug
from tunacode.core.logging import get_logger

from .sanitize import (
    TOOL_CALL_ID_ATTR,
)

__all__ = ["log_message_history_debug"]

DEBUG_HISTORY_MESSAGE_PREVIEW_LEN: int = 160
DEBUG_HISTORY_PART_PREVIEW_LEN: int = 120


def _format_tool_call_debug(tool_call: Any, max_len: int) -> str:
    """Format a tool call metadata entry for debug logging."""
    tool_name = _get_attr(tool_call, "tool_name")
    tool_call_id = _get_attr(tool_call, TOOL_CALL_ID_ATTR)
    args = _get_attr(tool_call, "args")

    segments: list[str] = []
    if tool_name:
        segments.append(f"tool={tool_name}")
    if tool_call_id:
        segments.append(f"id={tool_call_id}")

    args_preview, args_len = format_debug_preview(args, max_len)
    if args_preview:
        segments.append(f"args={args_preview} ({args_len} chars)")

    if not segments:
        segments.append("empty")

    return " ".join(segments)


def log_message_history_debug(
    messages: list[Any],
    user_message: str,
    dangling_tool_call_ids: set[ToolCallId],
) -> None:
    """Log a detailed history snapshot for debug tracing."""
    logger = get_logger()
    message_count = len(messages)
    dangling_count = len(dangling_tool_call_ids)
    logger.debug(f"History dump: messages={message_count} dangling_tool_calls={dangling_count}")

    if dangling_tool_call_ids:
        dangling_sorted = sorted(dangling_tool_call_ids)
        logger.debug(f"History dangling tool_call_ids: {dangling_sorted}")

    if user_message:
        preview, msg_len = format_debug_preview(
            user_message,
            DEBUG_HISTORY_MESSAGE_PREVIEW_LEN,
        )
        logger.debug(f"Outgoing user message: {preview} ({msg_len} chars)")

    for msg_index, message in enumerate(messages):
        msg_kind_value = _get_attr(message, "kind")
        msg_kind = msg_kind_value if msg_kind_value is not None else "unknown"
        parts = _get_parts(message)
        tool_calls = getattr(message, "tool_calls", []) or []
        tool_call_ids = get_tool_call_ids(message)
        tool_return_ids = get_tool_return_ids(message)

        part_count = len(parts)
        tool_call_count = len(tool_call_ids)
        tool_return_count = len(tool_return_ids)

        summary = (
            f"history[{msg_index}] kind={msg_kind} "
            f"parts={part_count} tool_calls={tool_call_count} "
            f"tool_returns={tool_return_count}"
        )
        if tool_call_ids:
            tool_call_sorted = sorted(tool_call_ids)
            summary = f"{summary} tool_call_ids={tool_call_sorted}"
        if tool_return_ids:
            tool_return_sorted = sorted(tool_return_ids)
            summary = f"{summary} tool_return_ids={tool_return_sorted}"
        logger.debug(summary)

        for part_index, part in enumerate(parts):
            part_summary = format_part_debug(part, DEBUG_HISTORY_PART_PREVIEW_LEN)
            logger.debug(f"history[{msg_index}].part[{part_index}] {part_summary}")

        for tool_index, tool_call in enumerate(tool_calls):
            tool_summary = _format_tool_call_debug(tool_call, DEBUG_HISTORY_PART_PREVIEW_LEN)
            logger.debug(f"history[{msg_index}].tool_calls[{tool_index}] {tool_summary}")
