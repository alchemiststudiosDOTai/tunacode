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

        session_id = state_manager.session.session_id

        # Act: save the session
        await registry.execute("/resume save", context)

        # Assert: file exists in the expected directory
        session_file = Path(tmp_home) / ".tunacode" / "sessions" / session_id / "session_state.json"
        assert session_file.exists(), f"Missing session file at {session_file}"

        # Mutate current session to verify load restores values
        state_manager.session.user_config = {}
        state_manager.session.current_model = "provider:other"
        state_manager.session.total_cost = 0.0
        state_manager.session.messages = []

        # Act: load using saved session id
        await registry.execute(f"/resume load {session_id}", context)

        # Verify essential fields restored
        assert state_manager.session.current_model == "provider:model-y"
        assert state_manager.session.user_config.get("default_model") == "provider:model-x"
        assert state_manager.session.total_cost == pytest.approx(3.14)
        assert len(state_manager.session.messages) == 2
