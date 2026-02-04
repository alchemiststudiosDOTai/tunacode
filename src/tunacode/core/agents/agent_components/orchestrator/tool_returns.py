"""Tool return emission for completed tool calls.

Handles emitting tool return events from model request parts.
"""

from typing import Any

from tunacode.types.callbacks import ToolResultCallback

from tunacode.core.logging import get_logger
from tunacode.core.types import StateManagerProtocol

from .debug_formatter import format_tool_return_debug

PART_KIND_TOOL_RETURN = "tool-return"
UNKNOWN_TOOL_NAME = "unknown"
TOOL_RESULT_STATUS_COMPLETED = "completed"


def consume_tool_call_args(part: Any, state_manager: StateManagerProtocol) -> Any:
    """Retrieve stored tool args for a tool return part.

    Delegates to tool_registry_ops for actual implementation.
    """
    from .tool_registry_ops import get_tool_args

    return get_tool_args(part, state_manager)


def emit_tool_returns(
    request: Any,
    state_manager: StateManagerProtocol,
    tool_result_callback: ToolResultCallback | None,
) -> None:
    """Process and emit tool return events from a request.

    Iterates through request parts, finds tool-return parts,
    and emits callbacks for each completed tool.

    Args:
        request: The model request containing tool return parts
        state_manager: Session state manager for registry access
        tool_result_callback: Optional callback to emit results
    """
    if not tool_result_callback:
        return

    request_parts = getattr(request, "parts", None)
    if not request_parts:
        return

    debug_mode = bool(getattr(state_manager.session, "debug_mode", False))
    logger = get_logger()

    for part in request_parts:
        part_kind = getattr(part, "part_kind", None)
        if part_kind != PART_KIND_TOOL_RETURN:
            continue

        tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
        logger.lifecycle(f"Tool return received (tool={tool_name})")

        tool_call_id = getattr(part, "tool_call_id", None)
        tool_args = consume_tool_call_args(part, state_manager)

        content = getattr(part, "content", None)
        result_str = str(content) if content is not None else None

        # Complete the tool in registry
        if tool_call_id:
            tool_registry = state_manager.session.runtime.tool_registry
            tool_registry.complete(tool_call_id, result_str)

        # Emit the callback
        tool_result_callback(
            tool_name,
            TOOL_RESULT_STATUS_COMPLETED,
            tool_args,
            result_str,
            None,
        )

        if debug_mode:
            debug_summary = format_tool_return_debug(
                tool_name,
                tool_call_id,
                tool_args,
                content,
            )
            logger.debug(debug_summary)
