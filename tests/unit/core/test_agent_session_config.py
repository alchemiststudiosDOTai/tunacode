from __future__ import annotations

from tunacode.core.agents.agent_components.agent_session_config import _normalize_session_config
from tunacode.core.session import StateManager


def test_normalize_session_config_includes_limit_settings(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    state_manager = StateManager()
    settings = state_manager.session.user_config["settings"]
    settings["max_command_output"] = 4321
    settings["max_tokens"] = 123

    config = _normalize_session_config(state_manager.session)

    assert config.settings.max_command_output == 4321
    assert config.settings.max_tokens == 123
