"""State transition operations for the orchestrator.

Centralizes all state machine transitions to eliminate
scattered state management across multiple modules.
"""

from tunacode.core.types import AgentState

from ..response_state import ResponseState


def transition_to_assistant(response_state: ResponseState | None) -> None:
    """Transition to ASSISTANT state if allowed."""
    if response_state is None:
        return
    if response_state.can_transition_to(AgentState.ASSISTANT):
        response_state.transition_to(AgentState.ASSISTANT)


def transition_to_tool_execution(response_state: ResponseState | None) -> None:
    """Transition to TOOL_EXECUTION state if allowed."""
    if response_state is None:
        return
    if response_state.can_transition_to(AgentState.TOOL_EXECUTION):
        response_state.transition_to(AgentState.TOOL_EXECUTION)


def transition_to_response(response_state: ResponseState | None) -> None:
    """Transition to RESPONSE state if allowed and not completed."""
    if response_state is None:
        return
    if response_state.can_transition_to(AgentState.RESPONSE) and not response_state.is_completed():
        response_state.transition_to(AgentState.RESPONSE)


def mark_has_user_response(response_state: ResponseState | None, has_output: bool) -> None:
    """Mark that the response has user-facing output."""
    if response_state is None:
        return
    if has_output:
        response_state.has_user_response = True
