"""Acceptance test for /resume command save/load functionality."""

import pathlib
import tempfile
from pathlib import Path

import pytest

from tunacode.cli.commands import CommandRegistry
from tunacode.core.state import StateManager
from tunacode.types import CommandContext


@pytest.mark.asyncio
async def test_resume_save_and_load_roundtrip(monkeypatch):
    # Arrange: isolate ~/.tunacode into a temp HOME
    with tempfile.TemporaryDirectory() as tmp_home:
        monkeypatch.setattr(pathlib.Path, "home", lambda: Path(tmp_home))

        registry = CommandRegistry()
        state_manager = StateManager()

        # Populate essential fields
        state_manager.session.user_config = {
            "default_model": "provider:model-x",
            "settings": {"max_iterations": 7},
        }
        state_manager.session.current_model = "provider:model-y"
        state_manager.session.total_cost = 3.14
        state_manager.session.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

        # Minimal process_request stub (not used by /resume)
        async def noop_request(_text, _state_manager, output=True):
            return None

        context = CommandContext(state_manager=state_manager, process_request=noop_request)

        original_session_id = state_manager.session.session_id

        # Act: save the session
        await registry.execute("/resume save", context)

        # Get the potentially updated session ID after save
        current_session_id = state_manager.session.session_id

        # Assert: file exists in the expected directory (use current session ID)
        session_file = Path(tmp_home) / ".tunacode" / "sessions" / current_session_id / "session_state.json"
        assert session_file.exists(), f"Missing session file at {session_file}"

        # Mutate current session to verify load restores values
        state_manager.session.user_config = {}
        state_manager.session.current_model = "provider:other"
        state_manager.session.total_cost = 0.0
        state_manager.session.messages = []

        # Act: load using saved session id
        await registry.execute(f"/resume load {current_session_id}", context)

        # Verify essential fields restored
        assert state_manager.session.current_model == "provider:model-y"
        assert state_manager.session.user_config.get("default_model") == "provider:model-x"
        assert state_manager.session.total_cost == pytest.approx(3.14)
        assert len(state_manager.session.messages) == 2


@pytest.mark.asyncio
async def test_enhanced_message_serialization(monkeypatch):
    """Test that enhanced message serialization preserves tool calls and context."""
    with tempfile.TemporaryDirectory() as tmp_home:
        monkeypatch.setattr(pathlib.Path, "home", lambda: Path(tmp_home))

        registry = CommandRegistry()
        state_manager = StateManager()

        # Create enhanced messages with tool calls and parts
        state_manager.session.messages = [
            {
                "kind": "request",
                "parts": [
                    {
                        "part_kind": "user-prompt",
                        "role": "user",
                        "content": "Debug this Python script error"
                    }
                ]
            },
            {
                "kind": "response",
                "parts": [
                    {
                        "part_kind": "tool-call",
                        "tool_name": "read_file",
                        "tool_call_id": "call_123",
                        "args": {"file_path": "script.py"}
                    }
                ]
            },
            {
                "kind": "request",
                "parts": [
                    {
                        "part_kind": "tool-return",
                        "tool_name": "read_file",
                        "tool_call_id": "call_123",
                        "content": "def main():\n    print('hello')"
                    }
                ]
            }
        ]

        # Set other essential fields
        state_manager.session.current_model = "provider:model-test"
        state_manager.session.total_cost = 1.23

        context = CommandContext(
            state_manager=state_manager,
            process_request=lambda _text, _state_manager, output=True: None
        )

        session_id = state_manager.session.session_id

        # Save the session
        await registry.execute("/resume save", context)

        # Verify session ID was updated with description from messages
        new_session_id = state_manager.session.session_id
        assert new_session_id != session_id  # Should be regenerated
        assert "python" in new_session_id.lower() or "debug" in new_session_id.lower()

        # Clear session and reload
        state_manager.session.messages = []
        state_manager.session.current_model = "provider:other"

        # Load the session
        await registry.execute(f"/resume load {new_session_id}", context)

        # Verify enhanced message data was preserved
        loaded_messages = state_manager.session.messages
        assert len(loaded_messages) == 3

        # Check first message (user prompt)
        user_msg = loaded_messages[0]
        assert user_msg["kind"] == "request"
        assert len(user_msg["parts"]) == 1
        user_part = user_msg["parts"][0]
        assert user_part["part_kind"] == "user-prompt"
        assert user_part["content"] == "Debug this Python script error"

        # Check second message (tool call)
        tool_call_msg = loaded_messages[1]
        assert tool_call_msg["kind"] == "response"
        assert len(tool_call_msg["parts"]) == 1
        tool_part = tool_call_msg["parts"][0]
        assert tool_part["part_kind"] == "tool-call"
        assert tool_part["tool_name"] == "read_file"
        assert tool_part["tool_call_id"] == "call_123"
        assert tool_part["args"] == {"file_path": "script.py"}

        # Check third message (tool return)
        tool_return_msg = loaded_messages[2]
        assert tool_return_msg["kind"] == "request"
        tool_return_part = tool_return_msg["parts"][0]
        assert tool_return_part["part_kind"] == "tool-return"
        assert tool_return_part["tool_name"] == "read_file"
        assert tool_return_part["tool_call_id"] == "call_123"
        assert "def main():" in tool_return_part["content"]


@pytest.mark.asyncio
async def test_sensitive_data_filtering(monkeypatch):
    """Test that sensitive data is filtered from serialized messages."""
    with tempfile.TemporaryDirectory() as tmp_home:
        monkeypatch.setattr(pathlib.Path, "home", lambda: Path(tmp_home))

        registry = CommandRegistry()
        state_manager = StateManager()

        # Create message with sensitive data in tool args
        state_manager.session.messages = [
            {
                "kind": "response",
                "parts": [
                    {
                        "part_kind": "tool-call",
                        "tool_name": "api_call",
                        "tool_call_id": "call_456",
                        "args": {
                            "url": "https://api.example.com",
                            "api_key": "secret-key-123",
                            "auth_token": "bearer-token-456",
                            "data": {"message": "hello"}
                        }
                    }
                ]
            }
        ]

        state_manager.session.current_model = "provider:model-test"

        context = CommandContext(
            state_manager=state_manager,
            process_request=lambda _text, _state_manager, output=True: None
        )

        # Save and reload
        await registry.execute("/resume save", context)
        session_id = state_manager.session.session_id

        state_manager.session.messages = []
        await registry.execute(f"/resume load {session_id}", context)

        # Verify sensitive data was filtered
        loaded_msg = state_manager.session.messages[0]
        tool_part = loaded_msg["parts"][0]
        args = tool_part["args"]

        # Should preserve non-sensitive data
        assert args["url"] == "https://api.example.com"
        assert args["data"] == {"message": "hello"}

        # Should filter sensitive data
        assert "api_key" not in args
        assert "auth_token" not in args
