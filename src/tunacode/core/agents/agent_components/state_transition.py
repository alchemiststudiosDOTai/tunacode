"""State transition management for agent response processing."""

import threading
from dataclasses import dataclass
from enum import Enum

from tunacode.types import AgentState


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, from_state: Enum, to_state: Enum, message: str | None = None):
        self.from_state = from_state
        self.to_state = to_state
        self.message = message or f"Invalid state transition: {from_state.value} → {to_state.value}"
        super().__init__(self.message)


@dataclass
class StateTransitionRules:
    """Defines valid state transitions for the agent state machine."""

    # Valid transitions for each state
    valid_transitions: dict[Enum, set[Enum]]

    def is_valid_transition(self, from_state: Enum, to_state: Enum) -> bool:
        """Check if a transition between states is valid."""
        return to_state in self.valid_transitions.get(from_state, set())

    def get_valid_next_states(self, current_state: Enum) -> set[Enum]:
        """Get all valid next states from the current state."""
        return self.valid_transitions.get(current_state, set())


class AgentStateMachine:
    """Thread-safe state machine for agent response processing."""

    def __init__(self, initial_state: "AgentState", rules: StateTransitionRules):
        """
        Initialize the state machine.

        Args:
            initial_state: The starting state
            rules: Transition rules defining valid state changes
        """
        self._state = initial_state
        self._rules = rules
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._completion_detected = False

    @property
    def current_state(self) -> "AgentState":
        """Get the current state."""
        with self._lock:
            return self._state

    def transition_to(self, new_state: "AgentState") -> None:
        """
        Transition to a new state.

        Args:
            new_state: The state to transition to

        Raises:
            InvalidStateTransitionError: If the transition is not valid
        """
        with self._lock:
            if not self._rules.is_valid_transition(self._state, new_state):
                raise InvalidStateTransitionError(
                    self._state,
                    new_state,
                    f"Invalid state transition: {self._state.value} → {new_state.value}",
                )

            # Handle self-transitions as no-ops
            if self._state == new_state:
                return

            self._state = new_state

    def can_transition_to(self, target_state: "AgentState") -> bool:
        """Check if a transition to the target state is allowed."""
        with self._lock:
            return self._rules.is_valid_transition(self._state, target_state)

    def set_completion_detected(self, detected: bool = True) -> None:
        """Mark that completion has been detected in the RESPONSE state."""
        with self._lock:
            self._completion_detected = detected

    def is_completed(self) -> bool:
        """Check if the task is completed (only valid in RESPONSE state)."""
        with self._lock:
            return self._state == AgentState.RESPONSE and self._completion_detected

    def reset(self, initial_state: "AgentState" = None) -> None:
        """Reset the state machine to initial state."""
        with self._lock:
            self._state = initial_state or AgentState.USER_INPUT
            self._completion_detected = False


# Define the transition rules for the agent state machine
AGENT_TRANSITION_RULES = StateTransitionRules(
    valid_transitions={
        AgentState.USER_INPUT: {AgentState.ASSISTANT},
        AgentState.ASSISTANT: {AgentState.TOOL_EXECUTION, AgentState.RESPONSE},
        AgentState.TOOL_EXECUTION: {AgentState.RESPONSE},
        AgentState.RESPONSE: {AgentState.ASSISTANT},  # Can transition back to continue
    }
)
