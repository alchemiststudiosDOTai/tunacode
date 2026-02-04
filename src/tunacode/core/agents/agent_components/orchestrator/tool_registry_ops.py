"""Tool registry operations - registration, tracking, and state management.

Isolates all tool registry interactions into a single module.
"""

from typing import Any

from tunacode.constants import (
    ERROR_TOOL_ARGS_MISSING,
    ERROR_TOOL_CALL_ID_MISSING,
)
from tunacode.exceptions import StateError, UserAbortError
from tunacode.types import ToolArgs, ToolCallId

from tunacode.core.types import StateManagerProtocol

UNKNOWN_TOOL_NAME = "unknown"
TOOL_FAILURE_TEMPLATE = "{error_type}: {error_message}"

# Characters that should never appear in valid tool names
INVALID_TOOL_NAME_CHARS = frozenset("<>(){}[]\"'`")


def is_suspicious_tool_name(tool_name: str) -> bool:
    """Check if a tool name looks malformed (contains special chars)."""
    if not tool_name:
        return True
    if len(tool_name) > 50:
        return True
    return any(c in INVALID_TOOL_NAME_CHARS for c in tool_name)


def normalize_tool_name(raw_tool_name: str | None) -> str:
    """Normalize tool names to avoid dispatch errors from whitespace."""
    if raw_tool_name is None:
        return UNKNOWN_TOOL_NAME

    normalized = raw_tool_name.strip()
    if not normalized:
        return UNKNOWN_TOOL_NAME

    return normalized


def register_tool_call(
    state_manager: StateManagerProtocol,
    tool_call_id: ToolCallId | None,
    tool_name: str,
    tool_args: ToolArgs,
) -> None:
    """Register a tool call in the runtime registry."""
    if not tool_call_id:
        return
    tool_registry = state_manager.session.runtime.tool_registry
    tool_registry.register(tool_call_id, tool_name, tool_args)


def mark_tools_running(
    state_manager: StateManagerProtocol,
    tasks: list[tuple[Any, Any]],
) -> None:
    """Mark tool calls as running for upcoming tasks."""
    tool_registry = state_manager.session.runtime.tool_registry
    for part, _ in tasks:
        tool_call_id = getattr(part, "tool_call_id", None)
        if tool_call_id:
            tool_registry.start(tool_call_id)


def record_tool_failure(
    state_manager: StateManagerProtocol,
    part: Any,
    error: BaseException,
) -> None:
    """Record a failed tool call in the registry."""
    tool_call_id = getattr(part, "tool_call_id", None)
    if not tool_call_id:
        return

    tool_registry = state_manager.session.runtime.tool_registry

    if isinstance(error, UserAbortError):
        tool_registry.cancel(tool_call_id, reason=str(error))
        return

    error_message = str(error)
    error_type = type(error).__name__
    error_detail = (
        TOOL_FAILURE_TEMPLATE.format(error_type=error_type, error_message=error_message)
        if error_message
        else error_type
    )
    tool_registry.fail(tool_call_id, error_detail)


def get_tool_args(part: Any, state_manager: StateManagerProtocol) -> ToolArgs:
    """Retrieve stored tool args for a tool return part."""
    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    if not tool_call_id:
        raise StateError(ERROR_TOOL_CALL_ID_MISSING)

    tool_registry = state_manager.session.runtime.tool_registry
    tool_args = tool_registry.get_args(tool_call_id)

    if tool_args is None:
        raise StateError(ERROR_TOOL_ARGS_MISSING.format(tool_call_id=tool_call_id))

    return tool_args


async def parse_and_register_args(part: Any, state_manager: StateManagerProtocol) -> ToolArgs:
    """Parse tool args and register the tool call in one operation."""
    from tunacode.tools.parsing.command_parser import parse_args

    raw_args = getattr(part, "args", {})
    parsed_args = await parse_args(raw_args)

    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    raw_tool_name = getattr(part, "tool_name", None)
    normalized_name = normalize_tool_name(raw_tool_name)

    # Update part if name was normalized
    if raw_tool_name != normalized_name:
        part.tool_name = normalized_name

    register_tool_call(state_manager, tool_call_id, normalized_name, parsed_args)
    return parsed_args
