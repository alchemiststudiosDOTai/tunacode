from typing import Any

from tunacode.tools.messaging import _get_attr

from tunacode.core.agents.resume.sanitize import (
    PART_KIND_ATTR,
    TOOL_CALL_ID_ATTR,
)

DEBUG_PREVIEW_SUFFIX: str = "..."
DEBUG_NEWLINE_REPLACEMENT: str = "\\n"


def format_debug_preview(value: Any, max_len: int) -> tuple[str, int]:
    """Format a debug preview with length metadata."""
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


def format_part_debug(part: Any, max_len: int) -> str:
    """Format a single part for debug logging."""
    part_kind_value = _get_attr(part, PART_KIND_ATTR)
    part_kind = part_kind_value if part_kind_value is not None else "unknown"
    tool_name = _get_attr(part, "tool_name")
    tool_call_id = _get_attr(part, TOOL_CALL_ID_ATTR)
    content = _get_attr(part, "content")
    args = _get_attr(part, "args")

    segments = [f"kind={part_kind}"]
    if tool_name:
        segments.append(f"tool={tool_name}")
    if tool_call_id:
        segments.append(f"id={tool_call_id}")

    content_preview, content_len = format_debug_preview(content, max_len)
    if content_preview:
        segments.append(f"content={content_preview} ({content_len} chars)")

    args_preview, args_len = format_debug_preview(args, max_len)
    if args_preview:
        segments.append(f"args={args_preview} ({args_len} chars)")

    return " ".join(segments)
