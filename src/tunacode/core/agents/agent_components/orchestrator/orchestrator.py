"""Node orchestration for agent responses."""

from collections.abc import Awaitable, Callable
from typing import Any

from tunacode.core.agents.resume.sanitize_debug import (
    DEBUG_NEWLINE_REPLACEMENT,
    DEBUG_PREVIEW_SUFFIX,
)
from tunacode.core.logging import get_logger
from tunacode.core.state import StateManager
from tunacode.types import AgentState
from tunacode.types.callbacks import ToolCallback, ToolStartCallback

from ..response_state import ResponseState
from ..tool_buffer import ToolBuffer
from ..truncation_checker import check_for_truncation
from .message_recorder import record_thought
from .tool_dispatcher import consume_tool_call_args, dispatch_tools, has_tool_calls
from .usage_tracker import update_usage

PART_KIND_TOOL_RETURN = "tool-return"
UNKNOWN_TOOL_NAME = "unknown"

CONTENT_JOINER = " "
EMPTY_RESPONSE_REASON_EMPTY = "empty"
EMPTY_RESPONSE_REASON_TRUNCATED = "truncated"

TOOL_RESULT_STATUS_COMPLETED = "completed"

# Preview length limits for debug logging
THOUGHT_PREVIEW_LENGTH = 80
RESPONSE_PREVIEW_LENGTH = 100
DEBUG_PART_PREVIEW_LENGTH = RESPONSE_PREVIEW_LENGTH

ToolResultCallback = Callable[..., None]
StreamingCallback = Callable[[str], Awaitable[None]]


def _emit_tool_returns(
    request: Any,
    state_manager: StateManager,
    tool_result_callback: ToolResultCallback | None,
) -> None:
    if not tool_result_callback:
        return

    request_parts = getattr(request, "parts", None)
    if not request_parts:
        return

    debug_mode = bool(getattr(state_manager.session, "debug_mode", False))

    for part in request_parts:
        part_kind = getattr(part, "part_kind", None)
        if part_kind != PART_KIND_TOOL_RETURN:
            continue

        logger = get_logger()
        tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
        logger.lifecycle(f"Tool return received (tool={tool_name})")
        tool_args = consume_tool_call_args(part, state_manager)
        content = getattr(part, "content", None)
        result_str = str(content) if content is not None else None
        tool_result_callback(
            tool_name=tool_name,
            status=TOOL_RESULT_STATUS_COMPLETED,
            args=tool_args,
            result=result_str,
        )

        if debug_mode:
            tool_call_id = getattr(part, "tool_call_id", None)
            debug_summary = _format_tool_return_debug(
                tool_name,
                tool_call_id,
                tool_args,
                content,
            )
            logger.debug(debug_summary)


def _format_debug_preview(value: Any) -> tuple[str, int]:
    """Return a trimmed preview string and its original length."""
    if value is None:
        return "", 0

    value_text = value if isinstance(value, str) else str(value)
    value_len = len(value_text)
    preview_len = min(DEBUG_PART_PREVIEW_LENGTH, value_len)
    preview_text = value_text[:preview_len]
    if value_len > preview_len:
        preview_text = f"{preview_text}{DEBUG_PREVIEW_SUFFIX}"
    preview_text = preview_text.replace("\n", DEBUG_NEWLINE_REPLACEMENT)
    return preview_text, value_len


def _format_part_debug(part: Any) -> str:
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

    content_preview, content_len = _format_debug_preview(content)
    if content_preview:
        segments.append(f"content={content_preview} ({content_len} chars)")

    args_preview, args_len = _format_debug_preview(args)
    if args_preview:
        segments.append(f"args={args_preview} ({args_len} chars)")

    return " ".join(segments)


def _log_model_request_parts(request: Any, debug_mode: bool) -> None:
    """Log the outgoing model request parts when debug is enabled."""
    if not debug_mode:
        return

    logger = get_logger()
    request_parts = getattr(request, "parts", None)
    request_type = type(request).__name__
    if request_parts is None:
        logger.debug(f"Model request parts: count=0 type={request_type} parts=None")
        return
    if not isinstance(request_parts, list):
        preview, preview_len = _format_debug_preview(request_parts)
        logger.debug(
            f"Model request parts: type={request_type} parts_type={type(request_parts).__name__} "
            f"preview={preview} ({preview_len} chars)"
        )
        return
    if not request_parts:
        logger.debug(f"Model request parts: count=0 type={request_type}")
        return

    request_part_count = len(request_parts)
    logger.debug(f"Model request parts: count={request_part_count} type={request_type}")
    for part_index, part in enumerate(request_parts):
        part_summary = _format_part_debug(part)
        logger.debug(f"Model request part[{part_index}]: {part_summary}")


def _format_tool_return_debug(
    tool_name: str,
    tool_call_id: str | None,
    tool_args: Any,
    content: Any,
) -> str:
    """Format tool return debug output."""
    segments = [f"tool={tool_name}"]
    if tool_call_id:
        segments.append(f"id={tool_call_id}")

    args_preview, args_len = _format_debug_preview(tool_args)
    if args_preview:
        segments.append(f"args={args_preview} ({args_len} chars)")

    result_preview, result_len = _format_debug_preview(content)
    if result_preview:
        segments.append(f"result={result_preview} ({result_len} chars)")

    return f"Tool return sent: {' '.join(segments)}"


async def process_node(
    node: Any,
    tool_callback: ToolCallback | None,
    state_manager: StateManager,
    _tool_buffer: ToolBuffer | None = None,
    _streaming_callback: StreamingCallback | None = None,
    response_state: ResponseState | None = None,
    tool_result_callback: ToolResultCallback | None = None,
    tool_start_callback: ToolStartCallback | None = None,
) -> tuple[bool, str | None]:
    """Process a single node from the agent response.

    Args:
        node: The agent response node to process.
        tool_callback: Callback to execute tools.
        state_manager: Session state manager.
        _tool_buffer: Unused. Preserved for API compatibility.
        _streaming_callback: Unused. Preserved for API compatibility.
        response_state: State machine for response tracking.
        tool_result_callback: Callback for tool result display.
        tool_start_callback: Callback for tool start display.

    Returns:
        Tuple of (is_empty, reason) where is_empty indicates a problematic
        response and reason is "empty" or "truncated".
    """
    empty_response_detected = False
    has_non_empty_content = False
    appears_truncated = False
    session = state_manager.session
    logger = get_logger()
    debug_mode = bool(getattr(state_manager.session, "debug_mode", False))

    if response_state and response_state.can_transition_to(AgentState.ASSISTANT):
        response_state.transition_to(AgentState.ASSISTANT)

    request = getattr(node, "request", None)
    if request is not None:
        _log_model_request_parts(request, debug_mode)
        _emit_tool_returns(request, state_manager, tool_result_callback)

    thought = getattr(node, "thought", None)
    if thought:
        record_thought(session, thought)
        # Log thought preview
        thought_preview = thought[:THOUGHT_PREVIEW_LENGTH].replace("\n", "\\n")
        if len(thought) > THOUGHT_PREVIEW_LENGTH:
            thought_preview += "..."
        logger.lifecycle(f"Thought: {thought_preview}")

    model_response = getattr(node, "model_response", None)
    if model_response is not None:
        update_usage(
            session,
            getattr(model_response, "usage", None),
            session.current_model,
        )

        response_parts = model_response.parts
        if debug_mode:
            response_part_count = len(response_parts)
            logger.debug(f"Model response parts: count={response_part_count}")
            for part_index, part in enumerate(response_parts):
                part_summary = _format_part_debug(part)
                logger.debug(f"Model response part[{part_index}]: {part_summary}")
        if response_state:
            has_structured_tools = has_tool_calls(response_parts)
            content_parts: list[str] = []

            for part in response_parts:
                content = getattr(part, "content", None)
                if not isinstance(content, str):
                    continue

                if content.strip():
                    has_non_empty_content = True
                    content_parts.append(content)

            if content_parts:
                combined_content = CONTENT_JOINER.join(content_parts).strip()
                appears_truncated = check_for_truncation(combined_content)

                # Log response preview for debug visibility
                preview_len = min(RESPONSE_PREVIEW_LENGTH, len(combined_content))
                preview = combined_content[:preview_len]
                if len(combined_content) > preview_len:
                    preview += "..."
                # Escape newlines for single-line output
                preview = preview.replace("\n", "\\n")
                logger.lifecycle(f"Response: {preview} ({len(combined_content)} chars)")

            no_tools = not has_structured_tools
            empty_without_tools = not has_non_empty_content and no_tools
            truncated_without_tools = appears_truncated and no_tools
            if empty_without_tools or truncated_without_tools:
                empty_response_detected = True

        await dispatch_tools(
            response_parts,
            node,
            state_manager,
            tool_callback,
            tool_result_callback,
            tool_start_callback,
            response_state,
        )

    if (
        response_state
        and response_state.can_transition_to(AgentState.RESPONSE)
        and not response_state.is_completed()
    ):
        response_state.transition_to(AgentState.RESPONSE)

    if empty_response_detected:
        reason = (
            EMPTY_RESPONSE_REASON_TRUNCATED if appears_truncated else EMPTY_RESPONSE_REASON_EMPTY
        )
        return True, reason

    return False, None
