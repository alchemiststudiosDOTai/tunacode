from __future__ import annotations

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG

STREAM_AGENT_TEXT_KEY = "stream_agent_text"


def test_default_user_config_disables_agent_text_streaming() -> None:
    settings = DEFAULT_USER_CONFIG["settings"]

    assert STREAM_AGENT_TEXT_KEY in settings
    assert settings[STREAM_AGENT_TEXT_KEY] is False
