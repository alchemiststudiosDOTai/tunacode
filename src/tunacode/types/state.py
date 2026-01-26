"""State management protocol for TunaCode CLI.

Defines the StateManager protocol to enable type-safe usage without
creating circular imports with the concrete implementation.
"""

from typing import TYPE_CHECKING, Any, Protocol

from tunacode.types.base import ToolArgs, ToolName
from tunacode.types.canonical import TodoItem
from tunacode.types.state_structures import (
    ConversationState,
    RuntimeState,
    TaskState,
    UsageState,
)

if TYPE_CHECKING:
    from tunacode.types.callbacks import PlanApprovalCallback, ToolProgressCallback
    from tunacode.types.dataclasses import ToolConfirmationRequest, ToolConfirmationResponse


class TodoProtocol(Protocol):
    """Protocol for todo tools to read/write todo state."""

    def get_todos(self) -> list[TodoItem]:
        """Get the current todo list."""
        ...

    def set_todos(self, todos: list[TodoItem]) -> None:
        """Replace the entire todo list."""
        ...

    def clear_todos(self) -> None:
        """Clear the todo list."""
        ...


class PlanSessionProtocol(Protocol):
    """Protocol for plan mode session state."""

    plan_mode: bool
    plan_approval_callback: "PlanApprovalCallback | None"


class PlanApprovalProtocol(Protocol):
    """Protocol for plan approval tools to access plan mode state."""

    @property
    def session(self) -> PlanSessionProtocol:
        """Access the current session state."""
        ...


class TemplateProtocol(Protocol):
    """Protocol for template metadata used in authorization."""

    allowed_tools: list[str]


class AuthorizationSessionProtocol(Protocol):
    """Protocol for authorization flows to access session state."""

    yolo: bool
    plan_mode: bool
    tool_ignore: list[ToolName]
    conversation: ConversationState

    def update_token_count(self) -> None:
        """Calculate total token count from conversation messages."""
        ...


class AuthorizationToolHandlerProtocol(Protocol):
    """Protocol for tool handlers exposing template context and authorization."""

    active_template: TemplateProtocol | None

    def should_confirm(self, tool_name: ToolName) -> bool:
        """Check if tool needs user confirmation."""
        ...

    def create_confirmation_request(
        self, tool_name: ToolName, args: ToolArgs
    ) -> "ToolConfirmationRequest":
        """Create a confirmation request for user approval."""
        ...

    def process_confirmation(
        self, response: "ToolConfirmationResponse", tool_name: ToolName
    ) -> bool:
        """Process user confirmation response. Returns True if approved."""
        ...


class AuthorizationProtocol(Protocol):
    """Protocol for authorization tools to access minimal state."""

    @property
    def session(self) -> AuthorizationSessionProtocol:
        """Access the current session state."""
        ...

    @property
    def tool_handler(self) -> AuthorizationToolHandlerProtocol | None:
        """Get the current tool handler."""
        ...

    def set_tool_handler(self, handler: AuthorizationToolHandlerProtocol) -> None:
        """Set the tool handler instance."""
        ...


class SessionStateProtocol(PlanSessionProtocol, AuthorizationSessionProtocol, Protocol):
    """Protocol for session state access."""

    user_config: dict[str, Any]
    current_model: str
    tool_progress_callback: "ToolProgressCallback | None"
    debug_mode: bool
    show_thoughts: bool
    task: TaskState
    runtime: RuntimeState
    usage: UsageState
    # Persistence fields
    session_id: str
    project_id: str
    created_at: str
    working_directory: str


class StateManagerProtocol(TodoProtocol, PlanApprovalProtocol, AuthorizationProtocol, Protocol):
    """Protocol defining the StateManager interface.

    This protocol enables type-safe references to StateManager without
    importing the concrete implementation, avoiding circular imports.
    """

    @property
    def session(self) -> SessionStateProtocol:
        """Access the current session state."""
        ...

    @property
    def tool_handler(self) -> AuthorizationToolHandlerProtocol | None:
        """Get the current tool handler."""
        ...

    def set_tool_handler(self, handler: AuthorizationToolHandlerProtocol) -> None:
        """Set the tool handler instance."""
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
    "AuthorizationProtocol",
    "AuthorizationSessionProtocol",
    "AuthorizationToolHandlerProtocol",
    "PlanApprovalProtocol",
    "PlanSessionProtocol",
    "SessionStateProtocol",
    "StateManagerProtocol",
    "TemplateProtocol",
    "TodoProtocol",
]
