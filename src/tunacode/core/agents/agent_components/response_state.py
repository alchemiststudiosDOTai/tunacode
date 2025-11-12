"""Response state management for tracking agent processing state."""

import threading
from dataclasses import dataclass, field
from typing import Optional

from tunacode.types import AgentState

from .state_transition import AGENT_TRANSITION_RULES, AgentStateMachine


@dataclass
class ResponseState:
    """Enhanced response state using enum-based state machine."""

    # Internal state machine
    _state_machine: AgentStateMachine = field(
        default_factory=lambda: AgentStateMachine(AgentState.USER_INPUT, AGENT_TRANSITION_RULES)
    )

    # Backward compatibility boolean flags (derived from enum state)
    _has_user_response: bool = False
    _task_completed: bool = False
    _awaiting_user_guidance: bool = False
    _has_final_synthesis: bool = False
    # Thread-safe lock for boolean flag access
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def __post_init__(self):
        """Initialize the state machine."""
        if not hasattr(self, "_state_machine"):
            self._state_machine = AgentStateMachine(AgentState.USER_INPUT, AGENT_TRANSITION_RULES)
        if not hasattr(self, "_lock"):
            self._lock = threading.RLock()

    @property
    def current_state(self) -> AgentState:
        """Get the current enum state."""
        return self._state_machine.current_state

    def transition_to(self, new_state: AgentState) -> None:
        """Transition to a new state."""
        self._state_machine.transition_to(new_state)

    def can_transition_to(self, target_state: AgentState) -> bool:
        """Check if a transition to the target state is allowed."""
        return self._state_machine.can_transition_to(target_state)

    # Backward compatibility properties
    @property
    def has_user_response(self) -> bool:
        """Legacy boolean flag for user response detection."""
        with self._lock:
            return self._has_user_response

    @has_user_response.setter
    def has_user_response(self, value: bool) -> None:
        """Set the legacy has_user_response flag."""
        with self._lock:
            self._has_user_response = value

    @property
    def task_completed(self) -> bool:
        """Legacy boolean flag for task completion (derived from state machine)."""
        with self._lock:
            # If explicitly set true, honor it; otherwise derive from state machine
            return bool(self._task_completed or self._state_machine.is_completed())

    @task_completed.setter
    def task_completed(self, value: bool) -> None:
        """Set the legacy task_completed flag and sync with state machine."""
        with self._lock:
            self._task_completed = bool(value)
            if value:
                # Ensure state reflects completion in RESPONSE
                try:
                    if (
                        self._state_machine.current_state != AgentState.RESPONSE
                        and self._state_machine.can_transition_to(AgentState.RESPONSE)
                    ):
                        self._state_machine.transition_to(AgentState.RESPONSE)
                except Exception:
                    # Best-effort: ignore invalid transition in legacy paths
                    pass
                self._state_machine.set_completion_detected(True)
            else:
                self._state_machine.set_completion_detected(False)

    @property
    def awaiting_user_guidance(self) -> bool:
        """Legacy boolean flag for awaiting user guidance."""
        with self._lock:
            return self._awaiting_user_guidance

    @awaiting_user_guidance.setter
    def awaiting_user_guidance(self, value: bool) -> None:
        """Set the legacy awaiting_user_guidance flag."""
        with self._lock:
            self._awaiting_user_guidance = value

    @property
    def has_final_synthesis(self) -> bool:
        """Legacy boolean flag for final synthesis."""
        with self._lock:
            return self._has_final_synthesis

    @has_final_synthesis.setter
    def has_final_synthesis(self, value: bool) -> None:
        """Set the legacy has_final_synthesis flag."""
        with self._lock:
            self._has_final_synthesis = value

    # Enhanced state management methods
    def set_completion_detected(self, detected: bool = True) -> None:
        """Mark that completion has been detected in the RESPONSE state."""
        self._state_machine.set_completion_detected(detected)

    def is_completed(self) -> bool:
        """Check if the task is completed according to the state machine."""
        return self._state_machine.is_completed()

    def reset_state(self, initial_state: Optional[AgentState] = None) -> None:
        """Reset the state machine to initial state."""
        with self._lock:
            self._state_machine.reset(initial_state)
            # Reset legacy flags
            self._has_user_response = False
            self._task_completed = False
            self._awaiting_user_guidance = False
            self._has_final_synthesis = False
