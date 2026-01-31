"""Tests for StateManager session persistence without pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tunacode.configuration import paths as configuration_paths
from tunacode.types.canonical import CanonicalMessage, MessageRole, TextPart
from tunacode.utils.messaging import to_wire_message

from tunacode.core.state import StateManager

PROJECT_ID = "test-project"
WORKING_DIRECTORY = "/tmp"


def test_save_load_session_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Persisted sessions should round-trip using canonical wire dicts."""
    monkeypatch.setattr(configuration_paths, "get_session_storage_dir", lambda: tmp_path)

    state_manager = StateManager()
    session = state_manager.session
    session.project_id = PROJECT_ID
    session.created_at = datetime.now(UTC).isoformat()
    session.working_directory = WORKING_DIRECTORY

    user_message = CanonicalMessage(
        role=MessageRole.USER,
        parts=(TextPart(content="Hello from user"),),
    )
    assistant_message = CanonicalMessage(
        role=MessageRole.ASSISTANT,
        parts=(TextPart(content="Hello from assistant"),),
    )

    session.conversation.messages = [
        to_wire_message(user_message),
        to_wire_message(assistant_message),
    ]

    saved = state_manager.save_session()
    assert saved is True

    reloaded_state = StateManager()
    monkeypatch.setattr(configuration_paths, "get_session_storage_dir", lambda: tmp_path)
    loaded = reloaded_state.load_session(session.session_id)

    assert loaded is True
    assert reloaded_state.session.conversation.messages == session.conversation.messages
    assert all(
        isinstance(message, dict) for message in reloaded_state.session.conversation.messages
    )
