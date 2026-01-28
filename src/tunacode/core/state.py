"""Module: tunacode.core.state

State management system for session data in TunaCode CLI.
Handles user preferences, conversation history, and runtime state.

CLAUDE_ANCHOR[state-module]: Central state management and session tracking
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.types import InputSessions, ModelName, SessionId, UserConfig
from tunacode.types.canonical import UsageMetrics
from tunacode.utils.messaging import estimate_tokens, get_content

from tunacode.core.types import ConversationState, RuntimeState, TaskState, UsageState


@dataclass
class SessionState:
    """CLAUDE_ANCHOR[session-state]: Core session state container"""

    user_config: UserConfig = field(default_factory=dict)
    agents: dict[str, Any] = field(
        default_factory=dict
    )  # Keep as dict[str, Any] for agent instances
    agent_versions: dict[str, int] = field(default_factory=dict)
    # Keep session default in sync with configuration default
    current_model: ModelName = DEFAULT_USER_CONFIG["default_model"]
    spinner: Any | None = None
    debug_mode: bool = False
    undo_initialized: bool = False
    show_thoughts: bool = False
    conversation: ConversationState = field(default_factory=ConversationState)
    task: TaskState = field(default_factory=TaskState)
    runtime: RuntimeState = field(default_factory=RuntimeState)
    usage: UsageState = field(default_factory=UsageState)
    session_id: SessionId = field(default_factory=lambda: str(uuid.uuid4()))
    input_sessions: InputSessions = field(default_factory=dict)
    current_task: Any | None = None
    # Persistence fields
    project_id: str = ""
    created_at: str = ""
    last_modified: str = ""
    working_directory: str = ""
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

    def update_token_count(self) -> None:
        """Calculate total token count from conversation messages."""
        messages = self.conversation.messages
        model_name = self.current_model
        total_tokens = 0

        for msg in messages:
            content = get_content(msg)
            if not content:
                continue
            token_count = estimate_tokens(content, model_name)
            total_tokens += token_count

        self.conversation.total_tokens = total_tokens

    def adjust_token_count(self, delta: int) -> None:
        """Adjust total_tokens by delta (negative for reclaimed tokens)."""
        updated_total = self.conversation.total_tokens + delta
        self.conversation.total_tokens = max(0, updated_total)


class StateManager:
    """CLAUDE_ANCHOR[state-manager]: Main state manager singleton"""

    def __init__(self) -> None:
        self._session = SessionState()
        self._load_user_configuration()

    def _load_user_configuration(self) -> None:
        """Load user configuration from file and merge with defaults."""
        from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
        from tunacode.configuration.models import get_model_context_window
        from tunacode.configuration.user_config import load_config_with_defaults

        # No config file - setup will be shown and replace this reference
        default_user_config = DEFAULT_USER_CONFIG
        merged_user_config = load_config_with_defaults(default_user_config)
        self._session.user_config = merged_user_config

        # Update current_model to match the loaded user config
        if self._session.user_config.get("default_model"):
            self._session.current_model = self._session.user_config["default_model"]

        # Initialize max_tokens from model's registry context window
        self._session.conversation.max_tokens = get_model_context_window(
            self._session.current_model
        )

    @property
    def session(self) -> SessionState:
        return self._session

    @property
    def conversation(self) -> ConversationState:
        return self._session.conversation

    @property
    def task(self) -> TaskState:
        return self._session.task

    @property
    def runtime(self) -> RuntimeState:
        return self._session.runtime

    @property
    def usage(self) -> UsageState:
        return self._session.usage

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

    def reset_session(self) -> None:
        """Reset the session to a fresh state."""
        self._session = SessionState()

    # Session persistence methods

    def _get_session_file_path(self) -> Path:
        """Get the file path for current session."""
        from tunacode.configuration.paths import get_session_storage_dir

        storage_dir = get_session_storage_dir()
        return storage_dir / f"{self._session.project_id}_{self._session.session_id}.json"

    def _serialize_messages(self) -> list[dict]:
        """Serialize mixed message list to JSON-compatible dicts."""
        msg_adapter: Any | None = None
        try:
            from pydantic import TypeAdapter
            from pydantic_ai.messages import ModelMessage

            msg_adapter = TypeAdapter(ModelMessage)
        except ImportError:
            msg_adapter = None

        serialized_messages: list[dict] = []
        for msg in self._session.conversation.messages:
            if isinstance(msg, dict):
                serialized_messages.append(msg)
                continue

            if msg_adapter is None:
                message_type = type(msg).__name__
                raise TypeError(
                    f"Cannot serialize non-dict message without pydantic adapter: {message_type}"
                )

            serialized_message = msg_adapter.dump_python(msg, mode="json")
            serialized_messages.append(serialized_message)
        return serialized_messages

    def _deserialize_messages(self, data: list[dict]) -> list:
        """Deserialize JSON dicts back to message objects."""
        msg_adapter: Any | None = None
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

            if item.get("kind") in ("request", "response"):
                try:
                    result.append(msg_adapter.validate_python(item))
                except Exception:
                    result.append(item)
            else:
                result.append(item)
        return result

    def _split_thought_messages(self, messages: list[Any]) -> tuple[list[str], list[Any]]:
        """Separate thought entries from message history."""
        thoughts: list[str] = []
        cleaned_messages: list[Any] = []

        for message in messages:
            if isinstance(message, dict) and "thought" in message:
                thought_value = message.get("thought")
                if thought_value is not None:
                    thoughts.append(str(thought_value))
                continue

            cleaned_messages.append(message)

        return thoughts, cleaned_messages

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
            "total_tokens": self._session.conversation.total_tokens,
            "session_total_usage": self._session.usage.session_total_usage.to_dict(),
            "thoughts": self._session.conversation.thoughts,
            "messages": self._serialize_messages(),
        }

        try:
            session_file = self._get_session_file_path()
            session_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with open(session_file, "w") as f:
                json.dump(session_data, f, indent=2)
            return True
        except (PermissionError, OSError):
            return False

    def load_session(self, session_id: str) -> bool:
        """Load a session from disk."""
        from tunacode.configuration.models import get_model_context_window
        from tunacode.configuration.paths import get_session_storage_dir

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
            default_model = DEFAULT_USER_CONFIG["default_model"]
            self._session.current_model = data.get("current_model", default_model)
            # Update max_tokens based on loaded model's context window
            self._session.conversation.max_tokens = get_model_context_window(
                self._session.current_model
            )
            default_total_tokens = self._session.conversation.total_tokens
            self._session.conversation.total_tokens = data.get("total_tokens", default_total_tokens)
            self._session.usage.session_total_usage = UsageMetrics.from_dict(
                data.get("session_total_usage", {})
            )
            loaded_messages = self._deserialize_messages(data.get("messages", []))
            stored_thoughts = data.get("thoughts") or []
            extracted_thoughts, cleaned_messages = self._split_thought_messages(loaded_messages)
            self._session.conversation.thoughts = [*stored_thoughts, *extracted_thoughts]
            self._session.conversation.messages = cleaned_messages

            return True
        except json.JSONDecodeError:
            return False
        except Exception:
            return False

    def list_sessions(self) -> list[dict]:
        """List available sessions for current project."""
        from tunacode.configuration.paths import get_session_storage_dir

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
