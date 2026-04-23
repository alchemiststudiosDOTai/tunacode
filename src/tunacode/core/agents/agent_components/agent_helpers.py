"""Helper functions for agent operations to reduce code duplication."""

from __future__ import annotations

from collections.abc import Mapping

RECENT_TOOL_LIMIT = 3

ToolArgsView = Mapping[str, object]
ToolCallView = Mapping[str, object]


def _describe_read_file(tool_args: ToolArgsView) -> str:
    path_value = tool_args.get("file_path", tool_args.get("filepath", ""))
    path = path_value if isinstance(path_value, str) else ""
    return f"Reading `{path}`" if path else "Reading file"


def _coerce_tool_args(value: object) -> ToolArgsView:
    if not isinstance(value, dict):
        raise TypeError(f"tool args must be a dict[str, object], got {type(value).__name__}")

    coerced_args: dict[str, object] = {}
    for key, raw_value in value.items():
        if not isinstance(key, str):
            raise TypeError(f"tool args keys must be strings, got key of type {type(key).__name__}")
        coerced_args[key] = raw_value
    return coerced_args


def get_tool_description(tool_name: str, tool_args: ToolArgsView) -> str:
    """Get a descriptive string for a tool call."""
    if tool_name != "read_file":
        return tool_name
    path_value = tool_args.get("file_path", tool_args.get("filepath", ""))
    path = path_value if isinstance(path_value, str) else ""
    return f"{tool_name}('{path}')"


def get_readable_tool_description(tool_name: str, tool_args: ToolArgsView) -> str:
    """Get a human-readable description of a tool operation for batch panel display."""
    if tool_name == "read_file":
        return _describe_read_file(tool_args)
    return f"Executing `{tool_name}`"


def get_recent_tools_context(tool_calls: list[ToolCallView], limit: int = RECENT_TOOL_LIMIT) -> str:
    """Get a context string describing recent tool usage."""
    if not tool_calls:
        return "No tools used yet"

    recent_descriptions = [
        get_tool_description(
            str(tool_call.get("tool", "")),
            _coerce_tool_args(tool_call.get("args", {})),
        )
        for tool_call in tool_calls[-limit:]
    ]
    return f"Recent tools: {', '.join(recent_descriptions)}"
