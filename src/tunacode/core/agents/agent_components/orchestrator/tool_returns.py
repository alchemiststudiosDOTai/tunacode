"""Process inbound tool-return parts from model requests.

Handles the results of tools that ran in a previous iteration,
completing their lifecycle in the registry and notifying callbacks.
"""

from typing import Any

from tunacode.types.callbacks import ToolResultCallback

from tunacode.core.logging import get_logger
from tunacode.core.types import StateManagerProtocol

from .debug_format import format_tool_return
from .tool_dispatcher import consume_tool_call_args

PART_KIND_TOOL_RETURN = "tool-return"
UNKNOWN_TOOL_NAME = "unknown"
TOOL_RESULT_STATUS_COMPLETED = "completed"


def emit_tool_returns(
    request: Any,
    state_manager: StateManagerProtocol,
    tool_result_callback: ToolResultCallback | None,
) -> None:
    """Process tool-return parts from a model request, completing their lifecycle."""
    if not tool_result_callback:
        return

    parts = getattr(request, "parts", None)
    if not parts:
        return

    debug_mode = bool(getattr(state_manager.session, "debug_mode", False))
    logger = get_logger()

    for part in parts:
        if getattr(part, "part_kind", None) != PART_KIND_TOOL_RETURN:
            continue

        tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
        logger.lifecycle(f"Tool return received (tool={tool_name})")

        tool_call_id = getattr(part, "tool_call_id", None)
        tool_args = consume_tool_call_args(part, state_manager)
        content = getattr(part, "content", None)
        result_str = str(content) if content is not None else None

        if tool_call_id:
            state_manager.session.runtime.tool_registry.complete(tool_call_id, result_str)

        tool_result_callback(
            tool_name,
            TOOL_RESULT_STATUS_COMPLETED,
            tool_args,
            result_str,
            None,
        )

        if debug_mode:
            logger.debug(format_tool_return(tool_name, tool_call_id, tool_args, content))
