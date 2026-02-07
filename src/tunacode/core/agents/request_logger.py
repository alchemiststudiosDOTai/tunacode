"""Request logging utilities for agent processing."""

from __future__ import annotations

from typing import Any

DEBUG_HISTORY_SAMPLE_SIZE: int = 3
DEBUG_HISTORY_PARTS_LIMIT: int = 5


def log_history_state(
    session_messages: list[Any],
    baseline_message_count: int,
    logger: Any,
) -> None:
    """Log the current history state for corruption diagnostics."""
    if not session_messages:
        return

    last_msg = session_messages[-1]
    last_kind = getattr(last_msg, "kind", "unknown")
    last_parts = getattr(last_msg, "parts", [])
    last_parts_count = len(last_parts)
    has_tool_calls = message_has_tool_calls(last_msg)
    logger.debug(
        f"History state: {baseline_message_count} messages, "
        f"last_kind={last_kind}, parts={last_parts_count}, "
        f"has_tool_calls={has_tool_calls}"
    )

    message_sample = session_messages[-DEBUG_HISTORY_SAMPLE_SIZE:]
    for idx, msg in enumerate(message_sample):
        msg_kind = getattr(msg, "kind", "?")
        msg_parts = getattr(msg, "parts", [])
        parts_summary = _format_parts_summary(msg_parts)
        reverse_index = DEBUG_HISTORY_SAMPLE_SIZE - idx
        parts_str = ", ".join(parts_summary)
        logger.debug(f"  msg[-{reverse_index}]: kind={msg_kind}, parts=[{parts_str}]")


def _format_parts_summary(msg_parts: list[Any]) -> list[str]:
    """Format message parts for debug logging."""
    parts_summary = []
    parts_to_log = msg_parts[:DEBUG_HISTORY_PARTS_LIMIT]
    for part in parts_to_log:
        part_kind = getattr(part, "part_kind", "?")
        part_content = getattr(part, "content", None)
        content_preview = ""
        if isinstance(part_content, str):
            content_preview = f":{len(part_content)}chars"
        parts_summary.append(f"{part_kind}{content_preview}")
    return parts_summary


def log_sanitized_history_state(
    message_history: list[Any],
    debug_mode: bool,
    logger: Any,
) -> None:
    """Log sanitized message history details for debug mode."""
    if not debug_mode:
        return

    type_names = (
        [type(m).__name__ for m in message_history[:DEBUG_HISTORY_SAMPLE_SIZE]]
        if message_history
        else []
    )
    logger.debug(f"message_history count={len(message_history)}, types={type_names}")
    if not message_history:
        return

    logger.debug(
        f"message_history[0]: {type(message_history[0]).__name__} "
        f"kind={getattr(message_history[0], 'kind', 'unknown')}"
    )
    if len(message_history) <= 1:
        return

    logger.debug(
        f"message_history[-1]: {type(message_history[-1]).__name__} "
        f"kind={getattr(message_history[-1], 'kind', 'unknown')}"
    )


def message_has_tool_calls(message: Any) -> bool:
    """Return True if message contains tool calls in parts or metadata.

    Handles both pydantic-ai message objects and raw dicts (from failed deserialization).
    """
    if isinstance(message, dict):
        parts = message.get("parts", [])
        tool_calls = message.get("tool_calls", [])
    else:
        parts = getattr(message, "parts", [])
        tool_calls = getattr(message, "tool_calls", [])

    if tool_calls:
        return True

    for part in parts:
        if isinstance(part, dict):
            part_kind = part.get("part_kind")
        else:
            part_kind = getattr(part, "part_kind", None)
        if part_kind == "tool-call":
            return True

    return False
