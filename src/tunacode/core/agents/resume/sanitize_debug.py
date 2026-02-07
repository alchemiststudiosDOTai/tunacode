"""Debug logging helpers for message history sanitization.

This module is intentionally tinyagent-only.
It logs message roles, content previews, and tool call/return IDs to help trace
history cleanup decisions.
"""

from __future__ import annotations

from typing import Any

from tunacode.types import ToolCallId
from tunacode.utils.messaging import get_content, get_tool_call_ids, get_tool_return_ids

from tunacode.core.logging import get_logger

__all__ = ["log_message_history_debug"]

DEBUG_PREVIEW_SUFFIX: str = "..."
DEBUG_NEWLINE_REPLACEMENT: str = "\\n"
DEBUG_HISTORY_MESSAGE_PREVIEW_LEN: int = 160
DEBUG_HISTORY_CONTENT_ITEM_PREVIEW_LEN: int = 140

KEY_ROLE: str = "role"
KEY_CONTENT: str = "content"
KEY_TYPE: str = "type"


def _format_debug_preview(value: Any, max_len: int) -> tuple[str, int]:
    if value is None:
        return "", 0

    value_text = value if isinstance(value, str) else str(value)
    value_len = len(value_text)
    preview_len = min(max_len, value_len)
    preview_text = value_text[:preview_len]

    if value_len > preview_len:
        preview_text = f"{preview_text}{DEBUG_PREVIEW_SUFFIX}"

    preview_text = preview_text.replace("\n", DEBUG_NEWLINE_REPLACEMENT)
    return preview_text, value_len


def _format_content_item(item: Any) -> str:
    if item is None:
        return "None"

    if not isinstance(item, dict):
        return f"<{type(item).__name__}>"

    item_type = item.get(KEY_TYPE)
    preview, _ = _format_debug_preview(item, DEBUG_HISTORY_CONTENT_ITEM_PREVIEW_LEN)
    return f"type={item_type!r} {preview}"


def log_message_history_debug(
    messages: list[Any],
    user_message: str,
    dangling_tool_call_ids: set[ToolCallId],
) -> None:
    logger = get_logger()

    message_count = len(messages)
    logger.debug(
        f"History dump: messages={message_count} "
        f"dangling_tool_calls={len(dangling_tool_call_ids)}"
    )

    if dangling_tool_call_ids:
        logger.debug(f"Dangling tool_call_ids: {sorted(dangling_tool_call_ids)}")

    if user_message:
        preview, msg_len = _format_debug_preview(user_message, DEBUG_HISTORY_MESSAGE_PREVIEW_LEN)
        logger.debug(f"Outgoing user message: {preview} ({msg_len} chars)")

    for idx, message in enumerate(messages):
        role = message.get(KEY_ROLE) if isinstance(message, dict) else None
        role_str = role if isinstance(role, str) else type(message).__name__

        content_text = ""
        try:
            content_text = get_content(message)
        except Exception as exc:  # noqa: BLE001 - debug helper
            content_text = f"<content_error {type(exc).__name__}: {exc}>"

        content_preview, content_len = _format_debug_preview(
            content_text,
            DEBUG_HISTORY_MESSAGE_PREVIEW_LEN,
        )

        tool_call_ids = get_tool_call_ids(message)
        tool_return_ids = get_tool_return_ids(message)

        logger.debug(
            f"history[{idx}] role={role_str!r} content={content_preview} "
            f"({content_len} chars) tool_calls={sorted(tool_call_ids)} "
            f"tool_returns={sorted(tool_return_ids)}"
        )

        if isinstance(message, dict):
            content_items = message.get(KEY_CONTENT)
            if isinstance(content_items, list) and content_items:
                for item_index, item in enumerate(content_items):
                    logger.debug(
                        f"history[{idx}].content[{item_index}] {_format_content_item(item)}"
                    )
