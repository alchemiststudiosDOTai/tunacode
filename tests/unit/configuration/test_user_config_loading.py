from __future__ import annotations

import json

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.configuration.user_config import load_config


def test_load_config_merges_missing_keys_from_defaults(
    monkeypatch,
    tmp_path,
) -> None:
    config_file = tmp_path / "tunacode.json"
    config_file.write_text(
        json.dumps(
            {
                "default_model": "openrouter:openai/gpt-4.1",
                "env": {
                    "OPENAI_API_KEY": "sk-test",
                },
                "settings": {
                    "theme": "tokyo-night",
                    "lsp": {
                        "enabled": False,
                    },
                },
            }
        )
    )

    class _TestApplicationSettings:
        def __init__(self) -> None:
            self.paths = type(
                "_TestPaths",
                (),
                {"config_dir": tmp_path, "config_file": config_file},
            )()

    monkeypatch.setattr(
        "tunacode.configuration.user_config.ApplicationSettings",
        _TestApplicationSettings,
    )

    loaded_config = load_config(DEFAULT_USER_CONFIG)

    assert loaded_config is not None
    assert loaded_config["recent_models"] == []
    assert loaded_config["env"]["OPENAI_API_KEY"] == "sk-test"
    assert loaded_config["env"]["ANTHROPIC_API_KEY"] == ""
    assert loaded_config["settings"]["theme"] == "tokyo-night"
    assert loaded_config["settings"]["stream_agent_text"] is False
    assert loaded_config["settings"]["lsp"]["enabled"] is False
    assert loaded_config["settings"]["lsp"]["timeout"] == 5.0
