"""Debug formatting utilities for orchestrator logging.

Separates debug output formatting from core orchestration logic.
All functions are pure - they take data and return formatted strings.
"""

from typing import Any

from tunacode.core.agents.resume.sanitize_debug import (
    DEBUG_NEWLINE_REPLACEMENT,
    DEBUG_PREVIEW_SUFFIX,
)

# Preview length limits
THOUGHT_PREVIEW_LENGTH = 80
RESPONSE_PREVIEW_LENGTH = 100
DEBUG_PART_PREVIEW_LENGTH = RESPONSE_PREVIEW_LENGTH


def format_preview(value: Any, max_length: int = DEBUG_PART_PREVIEW_LENGTH) -> tuple[str, int]:
    """Create a truncated preview string.

    Args:
        value: Value to format (converted to string if needed)
        max_length: Maximum preview length

    Returns:
        Tuple of (preview_string, original_length)
    """
    if value is None:
        return "", 0

    value_text = value if isinstance(value, str) else str(value)
    value_len = len(value_text)
    preview_len = min(max_length, value_len)
    preview_text = value_text[:preview_len]

    if value_len > preview_len:
        preview_text = f"{preview_text}{DEBUG_PREVIEW_SUFFIX}"

    preview_text = preview_text.replace("\n", DEBUG_NEWLINE_REPLACEMENT)
    return preview_text, value_len


def format_thought_preview(thought: str) -> str:
    """Format a thought for logging preview."""
    preview = thought[:THOUGHT_PREVIEW_LENGTH].replace("\n", "\\n")
    if len(thought) > THOUGHT_PREVIEW_LENGTH:
        preview += "..."
    return preview


def format_response_preview(content: str) -> str:
    """Format response content for logging preview."""
    preview_len = min(RESPONSE_PREVIEW_LENGTH, len(content))
    preview = content[:preview_len]
    if len(content) > preview_len:
        preview += "..."
    preview = preview.replace("\n", "\\n")
    return preview


def format_part_debug(part: Any) -> str:
    """Format a request/response part for debug logging."""
    part_kind_value = getattr(part, "part_kind", None)
    part_kind = part_kind_value if part_kind_value is not None else "unknown"
    tool_name = getattr(part, "tool_name", None)
    tool_call_id = getattr(part, "tool_call_id", None)
    content = getattr(part, "content", None)
    args = getattr(part, "args", None)

    segments = [f"kind={part_kind}"]

    if tool_name:
        segments.append(f"tool={tool_name}")
    if tool_call_id:
        segments.append(f"id={tool_call_id}")

    content_preview, content_len = format_preview(content)
    if content_preview:
        segments.append(f"content={content_preview} ({content_len} chars)")

    args_preview, args_len = format_preview(args)
    if args_preview:
        segments.append(f"args={args_preview} ({args_len} chars)")

    return " ".join(segments)


def format_tool_return_debug(
    tool_name: str,
    tool_call_id: str | None,
    tool_args: Any,
    content: Any,
) -> str:
    """Format tool return information for debug output."""
    segments = [f"tool={tool_name}"]

    if tool_call_id:
        segments.append(f"id={tool_call_id}")

    args_preview, args_len = format_preview(tool_args)
    if args_preview:
        segments.append(f"args={args_preview} ({args_len} chars)")

    result_preview, result_len = format_preview(content)
    if result_preview:
        segments.append(f"result={result_preview} ({result_len} chars)")

    return f"Tool return sent: {' '.join(segments)}"
