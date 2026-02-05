"""Node orchestration for agent responses.

Thin coordinator that processes one node from pydantic-ai's agent loop.
Each step is a single function call delegated to a focused module:

  1. Transition to ASSISTANT state
  2. Process inbound tool returns from request
  3. Record agent thought
  4. Track token usage from model response
  5. Extract text content from response
  6. Dispatch outbound tool calls
  7. Check for node result (user response)
  8. Transition to RESPONSE state

All debug formatting lives in debug_format.py.
All tool return processing lives in tool_returns.py.
All tool dispatch logic lives in tool_dispatcher.py.
"""

from typing import Any

from tunacode.types.callbacks import (
    StreamingCallback,
    ToolCallback,
    ToolResultCallback,
    ToolStartCallback,
)

from tunacode.core.logging import get_logger
from tunacode.core.types import AgentState, StateManagerProtocol

from ..response_state import ResponseState
from .debug_format import log_request_parts, log_response_parts
from .message_recorder import record_thought
from .tool_dispatcher import dispatch_tools, has_tool_calls
from .tool_returns import emit_tool_returns
from .usage_tracker import update_usage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTENT_JOINER = " "
EMPTY_RESPONSE_REASON = "empty"

THOUGHT_PREVIEW_LENGTH = 80
RESPONSE_PREVIEW_LENGTH = 100

# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------


def _extract_text_content(parts: list[Any]) -> tuple[bool, str]:
    """Extract and join text content from response parts.

    Returns:
        (has_content, combined_text) where has_content is True if any
        non-empty text was found.
    """
    segments: list[str] = []
    for part in parts:
        content = getattr(part, "content", None)
        if not isinstance(content, str):
            continue
        if content.strip():
            segments.append(content)

    if not segments:
        return False, ""

    return True, CONTENT_JOINER.join(segments).strip()


def _log_response_preview(text: str) -> None:
    """Log a truncated, escaped preview of response content."""
    logger = get_logger()
    preview = text[:RESPONSE_PREVIEW_LENGTH]
    if len(text) > RESPONSE_PREVIEW_LENGTH:
        preview += "..."
    preview = preview.replace("\n", "\\n")
    logger.lifecycle(f"Response: {preview} ({len(text)} chars)")


def _log_thought_preview(thought: str) -> None:
    """Log a truncated, escaped preview of agent thought."""
    logger = get_logger()
    preview = thought[:THOUGHT_PREVIEW_LENGTH].replace("\n", "\\n")
    if len(thought) > THOUGHT_PREVIEW_LENGTH:
        preview += "..."
    logger.lifecycle(f"Thought: {preview}")


# ---------------------------------------------------------------------------
# Empty response detection
# ---------------------------------------------------------------------------


def _detect_empty_response(
    has_content: bool,
    has_structured_tools: bool,
) -> bool:
    """Return True if the response has neither text content nor tool calls."""
    return not has_content and not has_structured_tools


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


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

    Returns:
        Tuple of (is_empty, reason) where is_empty indicates a problematic
        response and reason is "empty".
    """
    session = state_manager.session
    debug_mode = bool(getattr(session, "debug_mode", False))

    # Step 1: Transition to ASSISTANT
    if response_state and response_state.can_transition_to(AgentState.ASSISTANT):
        response_state.transition_to(AgentState.ASSISTANT)

    # Step 2: Process inbound request (tool returns from previous iteration)
    request = getattr(node, "request", None)
    if request is not None:
        log_request_parts(request, debug_mode)
        emit_tool_returns(request, state_manager, tool_result_callback)

    # Step 3: Record agent thought
    thought = getattr(node, "thought", None)
    if thought:
        record_thought(session, thought)
        _log_thought_preview(thought)

    # Step 4-7: Process model response (if present)
    model_response = getattr(node, "model_response", None)
    if model_response is None:
        return _finalize(response_state, is_empty=False)

    # Step 4: Track token usage
    update_usage(
        session,
        getattr(model_response, "usage", None),
        session.current_model,
    )

    response_parts = model_response.parts
    log_response_parts(response_parts, debug_mode)

    # Step 5: Extract text content
    has_content, combined_text = _extract_text_content(response_parts)
    if combined_text:
        _log_response_preview(combined_text)

    # Step 6: Detect empty response
    has_structured_tools = has_tool_calls(response_parts)
    is_empty = (
        _detect_empty_response(has_content, has_structured_tools) if response_state else False
    )

    # Step 7: Dispatch tool calls (state transition callback keeps ownership here)
    def _transition_to_tool_execution() -> None:
        if response_state and response_state.can_transition_to(AgentState.TOOL_EXECUTION):
            response_state.transition_to(AgentState.TOOL_EXECUTION)

    await dispatch_tools(
        response_parts,
        node,
        state_manager,
        tool_callback,
        tool_start_callback,
        response_state_transition=_transition_to_tool_execution,
    )

    # Step 8: Check for node result (user response detection)
    if response_state:
        result_output = getattr(getattr(node, "result", None), "output", None)
        if result_output:
            response_state.has_user_response = True

    return _finalize(response_state, is_empty)


def _finalize(
    response_state: ResponseState | None,
    is_empty: bool,
) -> tuple[bool, str | None]:
    """Transition to RESPONSE state and return the empty-detection result."""
    if (
        response_state
        and response_state.can_transition_to(AgentState.RESPONSE)
        and not response_state.is_completed()
    ):
        response_state.transition_to(AgentState.RESPONSE)

    if is_empty:
        return True, EMPTY_RESPONSE_REASON

    return False, None
