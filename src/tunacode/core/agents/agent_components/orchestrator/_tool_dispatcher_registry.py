"""Tool registry operations + tool-arg normalization for tool_dispatcher."""

from typing import Any

from tunacode.constants import ERROR_TOOL_ARGS_MISSING, ERROR_TOOL_CALL_ID_MISSING
from tunacode.exceptions import StateError, UserAbortError
from tunacode.types import ToolArgs, ToolCallId

from tunacode.core.types import StateManagerProtocol

from ._tool_dispatcher_constants import TOOL_FAILURE_TEMPLATE
from ._tool_dispatcher_names import _normalize_tool_name


def _register_tool_call(
    state_manager: StateManagerProtocol,
    tool_call_id: ToolCallId | None,
    tool_name: str,
    tool_args: ToolArgs,
) -> None:
    """Register a tool call in the runtime registry."""
    if not tool_call_id:
        return

    state_manager.session.runtime.tool_registry.register(tool_call_id, tool_name, tool_args)


def _mark_tool_calls_running(
    state_manager: StateManagerProtocol,
    tasks: list[tuple[Any, Any]],
) -> None:
    """Mark tool calls as running for upcoming tasks."""
    registry = state_manager.session.runtime.tool_registry
    for part, _ in tasks:
        tool_call_id = getattr(part, "tool_call_id", None)
        if tool_call_id:
            registry.start(tool_call_id)


def _record_tool_failure(
    state_manager: StateManagerProtocol,
    part: Any,
    error: BaseException,
) -> None:
    """Record a failed tool call in the registry."""
    tool_call_id = getattr(part, "tool_call_id", None)
    if not tool_call_id:
        return

    registry = state_manager.session.runtime.tool_registry
    if isinstance(error, UserAbortError):
        registry.cancel(tool_call_id, reason=str(error))
        return

    error_message = str(error)
    error_type = type(error).__name__
    error_detail = (
        TOOL_FAILURE_TEMPLATE.format(error_type=error_type, error_message=error_message)
        if error_message
        else error_type
    )
    registry.fail(tool_call_id, error_detail)


async def normalize_tool_args(raw_args: Any) -> ToolArgs:
    """Parse raw tool args into a normalized structure."""
    from tunacode.tools.parsing.command_parser import parse_args

    return await parse_args(raw_args)


async def record_tool_call_args(
    part: Any,
    state_manager: StateManagerProtocol,
    *,
    normalized_tool_name: str | None = None,
) -> ToolArgs:
    """Parse tool args and register the tool call.

    Notes:
        pydantic-ai message parts may be frozen. Avoid mutating `part` in-place.
        Instead, normalize the tool name for registry bookkeeping and let the
        dispatcher construct a normalized execution part when needed.
    """
    raw_args = getattr(part, "args", {})
    parsed_args = await normalize_tool_args(raw_args)

    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    raw_tool_name = getattr(part, "tool_name", None)
    tool_name = normalized_tool_name or _normalize_tool_name(raw_tool_name)

    _register_tool_call(state_manager, tool_call_id, tool_name, parsed_args)
    return parsed_args


def consume_tool_call_args(part: Any, state_manager: StateManagerProtocol) -> ToolArgs:
    """Retrieve stored tool args for a tool return part."""
    tool_call_id: ToolCallId | None = getattr(part, "tool_call_id", None)
    if not tool_call_id:
        raise StateError(ERROR_TOOL_CALL_ID_MISSING)

    tool_call_args = state_manager.session.runtime.tool_registry.get_args(tool_call_id)
    if tool_call_args is None:
        raise StateError(ERROR_TOOL_ARGS_MISSING.format(tool_call_id=tool_call_id))

    return tool_call_args
