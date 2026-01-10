"""Module: tunacode.core.state

State management system for session data in TunaCode CLI.
Handles user preferences, conversation history, and runtime state.

CLAUDE_ANCHOR[state-module]: Central state management and session tracking
"""

import json
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.types import (
    DeviceId,
    InputSessions,
    MessageHistory,
    ModelName,
    SessionId,
    ToolArgs,
    ToolCallId,
    ToolName,
    ToolProgressCallback,
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
    tool_progress_callback: ToolProgressCallback | None = None
    yolo: bool = False
    debug_mode: bool = False
    plan_mode: bool = False
    # Callback for present_plan tool to get user approval
    # Signature: async (plan_content: str) -> tuple[bool, str] (approved, feedback)
    plan_approval_callback: Any | None = None
    undo_initialized: bool = False
    show_thoughts: bool = False
    session_id: SessionId = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: DeviceId | None = None
    input_sessions: InputSessions = field(default_factory=dict)
    current_task: Any | None = None
    # Persistence fields
    project_id: str = ""
    created_at: str = ""
    last_modified: str = ""
    working_directory: str = ""
    # CLAUDE_ANCHOR[react-scratchpad]: Session scratchpad for ReAct tooling
    react_scratchpad: dict[str, Any] = field(default_factory=lambda: {"timeline": []})
    react_forced_calls: int = 0
    react_guidance: list[str] = field(default_factory=list)
    # CLAUDE_ANCHOR[todos]: Session todo list for task tracking
    todos: list[dict[str, Any]] = field(default_factory=list)
    # Operation state tracking
    operation_cancelled: bool = False
    # Enhanced tracking for thoughts display
    files_in_context: set[str] = field(default_factory=set)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_args_by_id: dict[ToolCallId, ToolArgs] = field(default_factory=dict)
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
    # Streaming debug instrumentation (see core/agents/agent_components/streaming.py)
    _debug_events: list[str] = field(default_factory=list)
    _debug_raw_stream_accum: str = ""
    # Request lifecycle metadata
    request_id: str = ""
    original_query: str = ""
    # Agent execution counters
    consecutive_empty_responses: int = 0
    batch_counter: int = 0

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
        from tunacode.configuration.models import get_model_context_window
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

        # Initialize max_tokens from model's registry context window
        self._session.max_tokens = get_model_context_window(self._session.current_model)

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

    # Todo list helpers
    def get_todos(self) -> list[dict[str, Any]]:
        """Return the current todo list."""
        return self._session.todos

    def set_todos(self, todos: list[dict[str, Any]]) -> None:
        """Replace the entire todo list."""
        self._session.todos = todos

    def clear_todos(self) -> None:
        """Clear the todo list."""
        self._session.todos = []

    def reset_session(self) -> None:
        """Reset the session to a fresh state."""
        self._session = SessionState()

    # Session persistence methods

    def _get_session_file_path(self) -> Path:
        """Get the file path for current session."""
        from tunacode.utils.system.paths import get_session_storage_dir

        storage_dir = get_session_storage_dir()
        return storage_dir / f"{self._session.project_id}_{self._session.session_id}.json"

    def _serialize_messages(self) -> list[dict]:
        """Serialize mixed message list to JSON-compatible dicts."""
        try:
            from pydantic import TypeAdapter
            from pydantic_ai.messages import ModelMessage

            msg_adapter = TypeAdapter(ModelMessage)
        except ImportError:
            msg_adapter = None

        result = []
        for msg in self._session.messages:
            if isinstance(msg, dict):
                result.append(msg)
            elif msg_adapter is not None:
                with suppress(TypeError, ValueError, AttributeError):
                    result.append(msg_adapter.dump_python(msg, mode="json"))
        return result

    def _deserialize_messages(self, data: list[dict]) -> list:
        """Deserialize JSON dicts back to message objects."""
        try:
            from pydantic import TypeAdapter
            from pydantic_ai.messages import ModelMessage

            msg_adapter = TypeAdapter(ModelMessage)
        except ImportError:
            return data

        result = []
        for item in data:
            if not isinstance(item, dict):
                result.append(item)
                continue

            if "thought" in item:
                result.append(item)
            elif item.get("kind") in ("request", "response"):
                try:
                    result.append(msg_adapter.validate_python(item))
                except Exception:
                    result.append(item)
            else:
                result.append(item)
        return result

    def save_session(self) -> bool:
        """Save current session to disk."""
        if not self._session.project_id:
            pass
            return False

        self._session.last_modified = datetime.now(UTC).isoformat()

        session_data = {
            "version": 1,
            "session_id": self._session.session_id,
            "project_id": self._session.project_id,
            "created_at": self._session.created_at,
            "last_modified": self._session.last_modified,
            "working_directory": self._session.working_directory,
            "current_model": self._session.current_model,
            "total_tokens": self._session.total_tokens,
            "session_total_usage": self._session.session_total_usage,
            "tool_ignore": self._session.tool_ignore,
            "yolo": self._session.yolo,
            "react_scratchpad": self._session.react_scratchpad,
            "todos": self._session.todos,
            "messages": self._serialize_messages(),
        }

        try:
            session_file = self._get_session_file_path()
            session_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with open(session_file, "w") as f:
                json.dump(session_data, f, indent=2)
            return True
        except PermissionError:
            return False
        except OSError:
            return False
        except Exception:
            return False

    def load_session(self, session_id: str) -> bool:
        """Load a session from disk."""
        from tunacode.configuration.models import get_model_context_window
        from tunacode.utils.system.paths import get_session_storage_dir

        storage_dir = get_session_storage_dir()

        session_file = None
        for file in storage_dir.glob(f"*_{session_id}.json"):
            session_file = file
            break

        if not session_file or not session_file.exists():
            return False

        try:
            with open(session_file) as f:
                data = json.load(f)

            self._session.session_id = data.get("session_id", session_id)
            self._session.project_id = data.get("project_id", "")
            self._session.created_at = data.get("created_at", "")
            self._session.last_modified = data.get("last_modified", "")
            self._session.working_directory = data.get("working_directory", "")
            self._session.current_model = data.get(
                "current_model", DEFAULT_USER_CONFIG["default_model"]
            )
            # Update max_tokens based on loaded model's context window
            self._session.max_tokens = get_model_context_window(self._session.current_model)
            self._session.total_tokens = data.get("total_tokens", 0)
            self._session.session_total_usage = data.get(
                "session_total_usage",
                {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0},
            )
            self._session.tool_ignore = data.get("tool_ignore", [])
            self._session.yolo = data.get("yolo", False)
            self._session.react_scratchpad = data.get("react_scratchpad", {"timeline": []})
            self._session.todos = data.get("todos", [])
            self._session.messages = self._deserialize_messages(data.get("messages", []))

            return True
        except json.JSONDecodeError:
            return False
        except Exception:
            return False

    def list_sessions(self) -> list[dict]:
        """List available sessions for current project."""
        from tunacode.utils.system.paths import get_session_storage_dir

        storage_dir = get_session_storage_dir()
        sessions: list[dict[str, Any]] = []

        if not self._session.project_id:
            return sessions

        for file in storage_dir.glob(f"{self._session.project_id}_*.json"):
            try:
                with open(file) as f:
                    data = json.load(f)
                sessions.append(
                    {
                        "session_id": data.get("session_id", ""),
                        "created_at": data.get("created_at", ""),
                        "last_modified": data.get("last_modified", ""),
                        "message_count": len(data.get("messages", [])),
                        "current_model": data.get("current_model", ""),
                        "file_path": str(file),
                    }
                )
            except Exception:
                pass

        sessions.sort(key=lambda x: x.get("last_modified", ""), reverse=True)
        return sessions
