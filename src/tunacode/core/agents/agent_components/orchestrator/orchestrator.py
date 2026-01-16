"""Node orchestration for agent responses."""

from collections.abc import Awaitable, Callable
from typing import Any

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

    for part in request_parts:
        part_kind = getattr(part, "part_kind", None)
        if part_kind != PART_KIND_TOOL_RETURN:
            continue

        tool_name = getattr(part, "tool_name", UNKNOWN_TOOL_NAME)
        tool_args = consume_tool_call_args(part, state_manager)
        content = getattr(part, "content", None)
        result_str = str(content) if content is not None else None
        tool_result_callback(
            tool_name=tool_name,
            status=TOOL_RESULT_STATUS_COMPLETED,
            args=tool_args,
            result=result_str,
        )


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

    if response_state and response_state.can_transition_to(AgentState.ASSISTANT):
        response_state.transition_to(AgentState.ASSISTANT)

    request = getattr(node, "request", None)
    if request is not None:
        _emit_tool_returns(request, state_manager, tool_result_callback)

    thought = getattr(node, "thought", None)
    if thought:
        record_thought(session, thought)

    model_response = getattr(node, "model_response", None)
    if model_response is not None:
        update_usage(
            session,
            getattr(model_response, "usage", None),
            session.current_model,
        )

        response_parts = model_response.parts
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
