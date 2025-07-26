"""Module: tunacode.core.state

State management system for session data in TunaCode CLI.
Handles user preferences, conversation history, and runtime state.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from tunacode.types import (
    DeviceId,
    InputSessions,
    MessageHistory,
    ModelName,
    SessionId,
    TodoItem,
    ToolName,
    UserConfig,
)
from tunacode.utils.message_utils import get_message_content
from tunacode.utils.token_counter import estimate_tokens


@dataclass
class SessionState:
    user_config: UserConfig = field(default_factory=dict)
    agents: dict[str, Any] = field(
        default_factory=dict
    )  # Keep as dict[str, Any] for agent instances
    messages: MessageHistory = field(default_factory=list)
    total_cost: float = 0.0
    current_model: ModelName = "openai:gpt-4o"
    spinner: Optional[Any] = None
    tool_ignore: list[ToolName] = field(default_factory=list)
    yolo: bool = False
    undo_initialized: bool = False
    show_thoughts: bool = False
    session_id: SessionId = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: Optional[DeviceId] = None
    input_sessions: InputSessions = field(default_factory=dict)
    current_task: Optional[Any] = None
    todos: list[TodoItem] = field(default_factory=list)
    # Enhanced tracking for thoughts display
    files_in_context: set[str] = field(default_factory=set)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    iteration_count: int = 0
    current_iteration: int = 0
    # Track streaming state to prevent spinner conflicts
    is_streaming_active: bool = False
    # Track streaming panel reference for tool handler access
    streaming_panel: Optional[Any] = None
    # Context window tracking (estimation based)
    total_tokens: int = 0
    max_tokens: int = 0
    # API usage tracking (actual from providers)
    last_call_usage: dict = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost": 0.0,
        }
    )
    session_total_usage: dict = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost": 0.0,
        }
    )
    # Recursive execution tracking
    current_recursion_depth: int = 0
    max_recursion_depth: int = 5
    parent_task_id: Optional[str] = None
    task_hierarchy: dict[str, Any] = field(default_factory=dict)
    iteration_budgets: dict[str, int] = field(default_factory=dict)
    recursive_context_stack: list[dict[str, Any]] = field(default_factory=list)

    def update_token_count(self):
        """Calculates the total token count from messages and files in context."""
        message_contents = [get_message_content(msg) for msg in self.messages]
        message_content = " ".join(c for c in message_contents if c)
        file_content = " ".join(self.files_in_context)
        self.total_tokens = estimate_tokens(message_content + file_content, self.current_model)


class StateManager:
    def __init__(self):
        self._session = SessionState()

    @property
    def session(self) -> SessionState:
        return self._session

    def add_todo(self, todo: TodoItem) -> None:
        self._session.todos.append(todo)

    def update_todo(self, todo_id: str, status: str) -> None:
        from datetime import datetime

        for todo in self._session.todos:
            if todo.id == todo_id:
                todo.status = status
                if status == "completed" and not todo.completed_at:
                    todo.completed_at = datetime.now()
                break

    def push_recursive_context(self, context: dict[str, Any]) -> None:
        """Push a new context onto the recursive execution stack."""
        self._session.recursive_context_stack.append(context)
        self._session.current_recursion_depth += 1

    def pop_recursive_context(self) -> Optional[dict[str, Any]]:
        """Pop the current context from the recursive execution stack."""
        if self._session.recursive_context_stack:
            self._session.current_recursion_depth = max(
                0, self._session.current_recursion_depth - 1
            )
            return self._session.recursive_context_stack.pop()
        return None

    def set_task_iteration_budget(self, task_id: str, budget: int) -> None:
        """Set the iteration budget for a specific task."""
        self._session.iteration_budgets[task_id] = budget

    def get_task_iteration_budget(self, task_id: str) -> int:
        """Get the iteration budget for a specific task."""
        return self._session.iteration_budgets.get(task_id, 10)  # Default to 10

    def can_recurse_deeper(self) -> bool:
        """Check if we can recurse deeper without exceeding limits."""
        return self._session.current_recursion_depth < self._session.max_recursion_depth

    def reset_recursive_state(self) -> None:
        """Reset all recursive execution state."""
        self._session.current_recursion_depth = 0
        self._session.parent_task_id = None
        self._session.task_hierarchy.clear()
        self._session.iteration_budgets.clear()
        self._session.recursive_context_stack.clear()

    def remove_todo(self, todo_id: str) -> None:
        self._session.todos = [todo for todo in self._session.todos if todo.id != todo_id]

    def clear_todos(self) -> None:
        self._session.todos = []

    def reset_session(self) -> None:
        """Reset the session to a fresh state."""
        self._session = SessionState()
