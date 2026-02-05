"""Tool-name normalization and validation helpers for tool_dispatcher."""

from ._tool_dispatcher_constants import (
    INVALID_TOOL_NAME_CHARS,
    MAX_TOOL_NAME_LENGTH,
    UNKNOWN_TOOL_NAME,
)


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
