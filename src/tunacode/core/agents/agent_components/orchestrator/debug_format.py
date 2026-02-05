"""Debug formatting helpers for orchestrator logging.

Pure functions that format parts, previews, and tool returns
for debug-mode log output. No state, no side effects.
"""

from typing import Any

from tunacode.core.agents.resume.sanitize_debug import (
    DEBUG_NEWLINE_REPLACEMENT,
    DEBUG_PREVIEW_SUFFIX,
)
from tunacode.core.logging import get_logger

# Preview length limits
PART_PREVIEW_LENGTH = 100
THOUGHT_PREVIEW_LENGTH = 80
RESPONSE_PREVIEW_LENGTH = 100


def format_preview(value: Any) -> tuple[str, int]:
    """Return a trimmed, newline-escaped preview string and its original length."""
    if value is None:
        return "", 0

    text = value if isinstance(value, str) else str(value)
    total_len = len(text)
    truncated = text[:PART_PREVIEW_LENGTH]
    if total_len > PART_PREVIEW_LENGTH:
        truncated = f"{truncated}{DEBUG_PREVIEW_SUFFIX}"
    escaped = truncated.replace("\n", DEBUG_NEWLINE_REPLACEMENT)
    return escaped, total_len


def format_part(part: Any) -> str:
    """Format a request/response part for debug logging."""
    kind = getattr(part, "part_kind", None) or "unknown"
    tool_name = getattr(part, "tool_name", None)
    tool_call_id = getattr(part, "tool_call_id", None)
    content = getattr(part, "content", None)
    args = getattr(part, "args", None)

    segments = [f"kind={kind}"]
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


def format_tool_return(
    tool_name: str,
    tool_call_id: str | None,
    tool_args: Any,
    content: Any,
) -> str:
    """Format tool return details for debug logging."""
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


def log_request_parts(request: Any, debug_mode: bool) -> None:
    """Log outgoing model request parts when debug is enabled."""
    if not debug_mode:
        return

    logger = get_logger()
    parts = getattr(request, "parts", None)
    request_type = type(request).__name__

    if parts is None:
        logger.debug(f"Model request parts: count=0 type={request_type} parts=None")
        return

    if not isinstance(parts, list):
        preview, preview_len = format_preview(parts)
        logger.debug(
            f"Model request parts: type={request_type} parts_type={type(parts).__name__} "
            f"preview={preview} ({preview_len} chars)"
        )
        return

    if not parts:
        logger.debug(f"Model request parts: count=0 type={request_type}")
        return

    logger.debug(f"Model request parts: count={len(parts)} type={request_type}")
    for idx, part in enumerate(parts):
        logger.debug(f"Model request part[{idx}]: {format_part(part)}")


def log_response_parts(parts: list[Any], debug_mode: bool) -> None:
    """Log model response parts when debug is enabled."""
    if not debug_mode:
        return

    logger = get_logger()
    logger.debug(f"Model response parts: count={len(parts)}")
    for idx, part in enumerate(parts):
        logger.debug(f"Model response part[{idx}]: {format_part(part)}")
