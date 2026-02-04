"""Node processor - the clean orchestrator core.

This is the rebuilt orchestrator following first principles:
- Single responsibility: coordinate node processing
- Clear data flow: extract -> process -> emit
- Delegates to specialized modules for each concern
"""

from typing import Any

from tunacode.types.callbacks import (
    StreamingCallback,
    ToolCallback,
    ToolResultCallback,
    ToolStartCallback,
)

from tunacode.core.logging import get_logger
from tunacode.core.types import StateManagerProtocol

from ..response_state import ResponseState
from ..truncation_checker import check_for_truncation
from . import state_ops
from .debug_formatter import format_part_debug, format_response_preview, format_thought_preview
from .extractors import (
    ExtractedContent,
    extract_content,
    extract_model_response,
    extract_request,
    extract_response_parts,
    extract_thought,
    extract_usage,
)
from .message_recorder import record_thought
from .tool_dispatch import dispatch_tools, has_tool_calls
from .tool_returns import emit_tool_returns
from .usage_tracker import update_usage

EMPTY_REASON_EMPTY = "empty"
EMPTY_REASON_TRUNCATED = "truncated"


def _log_request_parts(request: Any, debug_mode: bool) -> None:
    """Log outgoing model request parts when debug is enabled."""
    if not debug_mode:
        return

    logger = get_logger()
    request_parts = getattr(request, "parts", None)
    request_type = type(request).__name__

    if request_parts is None:
        logger.debug(f"Model request parts: count=0 type={request_type} parts=None")
        return

    if not isinstance(request_parts, list):
        from .debug_formatter import format_preview

        preview, preview_len = format_preview(request_parts)
        logger.debug(
            f"Model request parts: type={request_type} parts_type={type(request_parts).__name__} "
            f"preview={preview} ({preview_len} chars)"
        )
        return

    if not request_parts:
        logger.debug(f"Model request parts: count=0 type={request_type}")
        return

    logger.debug(f"Model request parts: count={len(request_parts)} type={request_type}")
    for idx, part in enumerate(request_parts):
        logger.debug(f"Model request part[{idx}]: {format_part_debug(part)}")


def _log_response_parts(response_parts: list[Any], debug_mode: bool) -> None:
    """Log response parts when debug is enabled."""
    if not debug_mode:
        return

    logger = get_logger()
    logger.debug(f"Model response parts: count={len(response_parts)}")
    for idx, part in enumerate(response_parts):
        logger.debug(f"Model response part[{idx}]: {format_part_debug(part)}")


def _process_thought(
    node: Any,
    session: Any,
) -> None:
    """Extract and record thought from node."""
    logger = get_logger()
    thought_data = extract_thought(node)

    if thought_data is None:
        return

    record_thought(session, thought_data.content)
    preview = format_thought_preview(thought_data.content)
    logger.lifecycle(f"Thought: {preview}")


def _process_usage(
    node: Any,
    session: Any,
    model_name: str,
) -> None:
    """Extract and update usage from node."""
    usage_data = extract_usage(node, model_name)
    if usage_data is None:
        return

    update_usage(session, usage_data.usage, usage_data.model_name)


def _check_empty_response(
    content: ExtractedContent,
    has_structured_tools: bool,
) -> tuple[bool, str | None]:
    """Determine if response is empty or truncated.

    Returns:
        Tuple of (is_problematic, reason)
    """
    no_tools = not has_structured_tools

    # Empty response without tools
    if not content.has_non_empty and no_tools:
        return True, EMPTY_REASON_EMPTY

    # Truncated response without tools
    if content.parts:
        combined = content.combined
        if check_for_truncation(combined) and no_tools:
            return True, EMPTY_REASON_TRUNCATED

    return False, None


def _log_content_preview(content: ExtractedContent) -> None:
    """Log content preview for visibility."""
    if not content.parts:
        return

    logger = get_logger()
    combined = content.combined
    preview = format_response_preview(combined)
    logger.lifecycle(f"Response: {preview} ({len(combined)} chars)")


async def process_node(
    node: Any,
    tool_callback: ToolCallback | None,
    state_manager: StateManagerProtocol,
    _streaming_callback: StreamingCallback | None = None,
    response_state: ResponseState | None = None,
    tool_result_callback: ToolResultCallback | None = None,
    tool_start_callback: ToolStartCallback | None = None,
) -> tuple[bool, str | None]:
    """Process a single node from the agent response.

    This is the main entry point - a thin coordinator that:
    1. Extracts data from the node
    2. Delegates processing to specialized modules
    3. Returns empty/truncation status

    Args:
        node: The agent response node to process
        tool_callback: Callback to execute tools
        state_manager: Session state manager
        _streaming_callback: Unused, preserved for API compatibility
        response_state: State machine for response tracking
        tool_result_callback: Callback for tool result display
        tool_start_callback: Callback for tool start display

    Returns:
        Tuple of (is_empty, reason) where is_empty indicates a problematic
        response and reason is "empty" or "truncated"
    """
    session = state_manager.session
    debug_mode = bool(getattr(session, "debug_mode", False))

    # Transition to assistant state
    state_ops.transition_to_assistant(response_state)

    # Handle request (tool returns)
    request = extract_request(node)
    if request is not None:
        _log_request_parts(request, debug_mode)
        emit_tool_returns(request, state_manager, tool_result_callback)

    # Process thought
    _process_thought(node, session)

    # Process model response
    model_response = extract_model_response(node)
    if model_response is None:
        state_ops.transition_to_response(response_state)
        return False, None

    # Update usage
    _process_usage(node, session, session.current_model)

    # Extract and analyze response parts
    response_parts = extract_response_parts(model_response)
    _log_response_parts(response_parts, debug_mode)

    # Check for empty/truncated response
    is_empty = False
    reason = None

    if response_state:
        has_structured = has_tool_calls(response_parts)
        content = extract_content(response_parts)
        _log_content_preview(content)

        is_empty, reason = _check_empty_response(content, has_structured)

    # Dispatch tools
    await dispatch_tools(
        response_parts,
        node,
        state_manager,
        tool_callback,
        tool_result_callback,
        tool_start_callback,
        response_state,
    )

    # Final state transition
    state_ops.transition_to_response(response_state)

    return is_empty, reason
