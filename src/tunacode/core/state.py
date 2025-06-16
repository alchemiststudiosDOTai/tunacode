"""Module: tunacode.core.state

State management system for session data in TunaCode CLI.
Handles user preferences, conversation history, and runtime state.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from tunacode.types import (DeviceId, InputSessions, MessageHistory, ModelName, SessionId, ToolName,
                            UserConfig)


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
    # Enhanced tracking for thoughts display
    files_in_context: set[str] = field(default_factory=set)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    iteration_count: int = 0
    current_iteration: int = 0


class StateManager:
    def __init__(self):
        self._session = SessionState()

    @property
    def session(self) -> SessionState:
        # Ensure files_in_context is always a set (fix for deserialization issues)
        if isinstance(self._session.files_in_context, list):
            self._session.files_in_context = set(self._session.files_in_context)
        return self._session

    def reset_session(self):
        self._session = SessionState()
