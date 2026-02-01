"""State management protocol for TunaCode CLI.

Defines the StateManager protocol to enable type-safe usage without
creating circular imports with the concrete implementation.
"""

from typing import Any, Protocol

from tunacode.core.types.state_structures import (
    ConversationState,
    RuntimeState,
    TaskState,
    UsageState,
)


class SessionStateProtocol(Protocol):
    """Protocol for session state access."""

    user_config: dict[str, Any]
    current_model: str
    debug_mode: bool
    show_thoughts: bool
    task: TaskState
    runtime: RuntimeState
    usage: UsageState
    conversation: ConversationState
    agents: dict[str, Any]
    agent_versions: dict[str, int]
    _debug_events: list[str]
    _debug_raw_stream_accum: str
    # Persistence fields
    session_id: str
    project_id: str
    created_at: str
    working_directory: str

    def update_token_count(self) -> None:
        """Calculate total token count from conversation messages."""
        ...


class StateManagerProtocol(Protocol):
    """Protocol defining the StateManager interface.

    This protocol enables type-safe references to StateManager without
    importing the concrete implementation, avoiding circular imports.
    """

    @property
    def session(self) -> SessionStateProtocol:
        """Access the current session state."""
        ...

    @property
    def conversation(self) -> ConversationState:
        """Access the conversation sub-state."""
        ...

    @property
    def task(self) -> TaskState:
        """Access the task sub-state."""
        ...

    @property
    def runtime(self) -> RuntimeState:
        """Access the runtime sub-state."""
        ...

    @property
    def usage(self) -> UsageState:
        """Access the usage sub-state."""
        ...

    # Recursive execution methods
    def push_recursive_context(self, context: dict[str, Any]) -> None:
        """Push a context onto the recursive stack."""
        ...

    def pop_recursive_context(self) -> dict[str, Any] | None:
        """Pop and return the top context."""
        ...

    def can_recurse_deeper(self) -> bool:
        """Check if recursion limit allows deeper nesting."""
        ...

    def reset_recursive_state(self) -> None:
        """Reset all recursive execution state."""
        ...

    # Session persistence methods
    async def save_session(self) -> bool:
        """Save current session to disk."""
        ...

    async def load_session(self, session_id: str) -> bool:
        """Load a session from disk by ID."""
        ...

    def list_sessions(self) -> list[dict[str, Any]]:
        """List available saved sessions."""
        ...


__all__ = [
    "SessionStateProtocol",
    "StateManagerProtocol",
]
