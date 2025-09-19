"""Module: tunacode.core.state

State management system for session data in TunaCode CLI.
Handles user preferences, conversation history, and runtime state.

CLAUDE_ANCHOR[state-module]: Central state management and session tracking
"""

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.types import (
    DeviceId,
    InputSessions,
    MessageHistory,
    ModelName,
    PlanDoc,
    PlanPhase,
    SessionId,
    TodoItem,
    ToolName,
    UserConfig,
)
from tunacode.utils.message_utils import get_message_content
from tunacode.utils.token_counter import estimate_tokens

if TYPE_CHECKING:
    from tunacode.core.tool_handler import ToolHandler


@dataclass
class SessionState:
    """CLAUDE_ANCHOR[session-state]: Core session state container"""

    user_config: UserConfig = field(default_factory=dict)
    agents: dict[str, Any] = field(
        default_factory=dict
    )  # Keep as dict[str, Any] for agent instances
    messages: MessageHistory = field(default_factory=list)
    total_cost: float = 0.0
    # Keep session default in sync with configuration default
    current_model: ModelName = DEFAULT_USER_CONFIG["default_model"]
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
    # CLAUDE_ANCHOR[react-scratchpad]: Session scratchpad for ReAct tooling
    react_scratchpad: dict[str, Any] = field(default_factory=lambda: {"timeline": []})
    react_forced_calls: int = 0
    react_guidance: list[str] = field(default_factory=list)
    # Operation state tracking
    operation_cancelled: bool = False
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

    # Plan Mode state tracking
    plan_mode: bool = False
    plan_phase: Optional[PlanPhase] = None
    current_plan: Optional[PlanDoc] = None
    plan_approved: bool = False

    def update_token_count(self):
        """Calculates the total token count from messages and files in context."""
        message_contents = [get_message_content(msg) for msg in self.messages]
        message_content = " ".join(c for c in message_contents if c)
        file_content = " ".join(self.files_in_context)
        self.total_tokens = estimate_tokens(message_content + file_content, self.current_model)


class StateManager:
    """CLAUDE_ANCHOR[state-manager]: Main state manager singleton"""

    def __init__(self):
        self._session = SessionState()
        self._tool_handler: Optional["ToolHandler"] = None

    @property
    def session(self) -> SessionState:
        return self._session

    @property
    def tool_handler(self) -> Optional["ToolHandler"]:
        return self._tool_handler

    def set_tool_handler(self, handler: "ToolHandler") -> None:
        self._tool_handler = handler

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
        self._session.current_recursion_depth = (self._session.current_recursion_depth or 0) + 1

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

    # React scratchpad helpers
    def get_react_scratchpad(self) -> dict[str, Any]:
        return self._session.react_scratchpad

    def append_react_entry(self, entry: dict[str, Any]) -> None:
        timeline = self._session.react_scratchpad.setdefault("timeline", [])
        timeline.append(entry)

    def clear_react_scratchpad(self) -> None:
        self._session.react_scratchpad = {"timeline": []}

    def reset_session(self) -> None:
        """Reset the session to a fresh state."""
        self._session = SessionState()

    # Plan Mode methods
    def enter_plan_mode(self) -> None:
        """Enter plan mode - restricts to read-only operations."""
        self._session.plan_mode = True
        self._session.plan_phase = PlanPhase.PLANNING_RESEARCH
        self._session.current_plan = None
        self._session.plan_approved = False
        # Clear agent cache to force recreation with plan mode tools
        self._session.agents.clear()

    def exit_plan_mode(self, plan: Optional[PlanDoc] = None) -> None:
        """Exit plan mode with optional plan data."""
        self._session.plan_mode = False
        self._session.plan_phase = None
        self._session.current_plan = plan
        self._session.plan_approved = False
        # Clear agent cache to force recreation without plan mode tools
        self._session.agents.clear()

    def approve_plan(self) -> None:
        """Mark current plan as approved for execution."""
        self._session.plan_approved = True
        self._session.plan_mode = False

    def is_plan_mode(self) -> bool:
        """Check if currently in plan mode."""
        return self._session.plan_mode

    def set_current_plan(self, plan: PlanDoc) -> None:
        """Set the current plan data."""
        self._session.current_plan = plan

    def get_current_plan(self) -> Optional[PlanDoc]:
        """Get the current plan data."""
        return self._session.current_plan
