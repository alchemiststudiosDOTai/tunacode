"""State management protocol for TunaCode CLI.

Defines the StateManager protocol to enable type-safe usage without
creating circular imports with the concrete implementation.
"""

from typing import TYPE_CHECKING, Any, Protocol

from tunacode.types.state_structures import (
    ConversationState,
    ReActState,
    RuntimeState,
    TaskState,
    UsageState,
)

if TYPE_CHECKING:
    from tunacode.types.callbacks import ToolProgressCallback


class SessionStateProtocol(Protocol):
    """Protocol for session state access."""

    user_config: dict[str, Any]
    current_model: str
    tool_progress_callback: "ToolProgressCallback | None"
    tool_ignore: list[str]
    yolo: bool
    debug_mode: bool
    plan_mode: bool
    plan_approval_callback: Any | None
    show_thoughts: bool
    conversation: ConversationState
    react: ReActState
    task: TaskState
    runtime: RuntimeState
    usage: UsageState
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
    def tool_handler(self) -> Any:
        """Get the current tool handler."""
        ...

    def set_tool_handler(self, handler: Any) -> None:
        """Set the tool handler instance."""
        ...

    @property
    def conversation(self) -> ConversationState:
        """Access the conversation sub-state."""
        ...

    @property
    def react(self) -> ReActState:
        """Access the ReAct sub-state."""
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

    # ReAct scratchpad methods
    def get_react_scratchpad(self) -> dict[str, Any]:
        """Get the ReAct scratchpad dictionary."""
        ...

    def append_react_entry(self, entry: dict[str, Any]) -> None:
        """Append an entry to the ReAct timeline."""
        ...

    def clear_react_scratchpad(self) -> None:
        """Clear the ReAct scratchpad."""
        ...

    # Todo list methods
    def get_todos(self) -> list[dict[str, Any]]:
        """Get the current todo list."""
        ...

    def set_todos(self, todos: list[dict[str, Any]]) -> None:
        """Replace the entire todo list."""
        ...

    def clear_todos(self) -> None:
        """Clear the todo list."""
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
    def save_session(self) -> bool:
        """Save current session to disk."""
        ...

    def load_session(self, session_id: str) -> bool:
        """Load a session from disk by ID."""
        ...

    def list_sessions(self) -> list[dict[str, Any]]:
        """List available saved sessions."""
        ...


__all__ = [
    "SessionStateProtocol",
    "StateManagerProtocol",
]
