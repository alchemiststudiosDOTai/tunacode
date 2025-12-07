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
    SessionId,
    ToolName,
    UserConfig,
)
from tunacode.utils.messaging import estimate_tokens, get_message_content

if TYPE_CHECKING:
    from tunacode.tools.authorization.handler import ToolHandler


@dataclass
class SessionState:
    """CLAUDE_ANCHOR[session-state]: Core session state container"""

    user_config: UserConfig = field(default_factory=dict)
    agents: dict[str, Any] = field(
        default_factory=dict
    )  # Keep as dict[str, Any] for agent instances
    agent_versions: dict[str, int] = field(default_factory=dict)
    messages: MessageHistory = field(default_factory=list)
    # Keep session default in sync with configuration default
    current_model: ModelName = DEFAULT_USER_CONFIG["default_model"]
    spinner: Any | None = None
    tool_ignore: list[ToolName] = field(default_factory=list)
    yolo: bool = False
    undo_initialized: bool = False
    show_thoughts: bool = False
    session_id: SessionId = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: DeviceId | None = None
    input_sessions: InputSessions = field(default_factory=dict)
    current_task: Any | None = None
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
    streaming_panel: Any | None = None
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
    parent_task_id: str | None = None
    task_hierarchy: dict[str, Any] = field(default_factory=dict)
    iteration_budgets: dict[str, int] = field(default_factory=dict)
    recursive_context_stack: list[dict[str, Any]] = field(default_factory=list)

    def update_token_count(self) -> None:
        """Calculate total token count from conversation messages."""
        total = 0
        for msg in self.messages:
            content = get_message_content(msg)
            if content:
                total += estimate_tokens(content, self.current_model)
        self.total_tokens = total

    def adjust_token_count(self, delta: int) -> None:
        """Adjust total_tokens by delta (negative for reclaimed tokens)."""
        self.total_tokens = max(0, self.total_tokens + delta)


class StateManager:
    """CLAUDE_ANCHOR[state-manager]: Main state manager singleton"""

    def __init__(self):
        self._session = SessionState()
        self._tool_handler: ToolHandler | None = None
        self._load_user_configuration()

    def _load_user_configuration(self) -> None:
        """Load user configuration from file and merge with defaults."""
        from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
        from tunacode.utils.config import load_config

        # Load user config from file
        user_config = load_config()
        if user_config:
            # Merge with defaults: user config takes precedence
            merged_config = DEFAULT_USER_CONFIG.copy()
            merged_config.update(user_config)

            # Merge nested settings
            if "settings" in user_config:
                merged_config["settings"] = DEFAULT_USER_CONFIG["settings"].copy()
                merged_config["settings"].update(user_config["settings"])

            # Update session with merged configuration
            self._session.user_config = merged_config
        else:
            # No user config file found, use defaults
            self._session.user_config = DEFAULT_USER_CONFIG.copy()

        # Update current_model to match the loaded user config
        if self._session.user_config.get("default_model"):
            self._session.current_model = self._session.user_config["default_model"]

        # Initialize max_tokens from config's context_window_size
        settings = self._session.user_config.get("settings", {})
        self._session.max_tokens = settings.get("context_window_size", 200000)

    @property
    def session(self) -> SessionState:
        return self._session

    @property
    def tool_handler(self) -> Optional["ToolHandler"]:
        return self._tool_handler

    def set_tool_handler(self, handler: "ToolHandler") -> None:
        self._tool_handler = handler

    def push_recursive_context(self, context: dict[str, Any]) -> None:
        """Push a new context onto the recursive execution stack."""
        self._session.recursive_context_stack.append(context)
        self._session.current_recursion_depth = (self._session.current_recursion_depth or 0) + 1

    def pop_recursive_context(self) -> dict[str, Any] | None:
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
