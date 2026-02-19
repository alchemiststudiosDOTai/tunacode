"""Tests that validate_provider_api_key falls back to OS environment."""

from __future__ import annotations

from tunacode.configuration.models import validate_provider_api_key


def test_validates_from_config(monkeypatch: object) -> None:
    """Key in user config is found."""
    config = {"env": {"OPENAI_API_KEY": "sk-test-123"}}
    is_valid, env_var = validate_provider_api_key("openai", config)
    assert is_valid is True
    assert env_var == "OPENAI_API_KEY"


def test_validates_from_os_env_when_config_empty(monkeypatch: object) -> None:
    """Key missing from config but present in OS env."""
    import os

    monkeypatch.setattr(os, "environ", {"MINIMAX_API_KEY": "mm-key-from-env"})  # type: ignore[attr-defined]
    config = {"env": {"MINIMAX_API_KEY": ""}}
    is_valid, env_var = validate_provider_api_key("minimax", config)
    assert is_valid is True
    assert env_var == "MINIMAX_API_KEY"


def test_invalid_when_missing_everywhere(monkeypatch: object) -> None:
    """Key missing from both config and OS env."""
    import os

    monkeypatch.setattr(os, "environ", {})  # type: ignore[attr-defined]
    config = {"env": {"MINIMAX_API_KEY": ""}}
    is_valid, env_var = validate_provider_api_key("minimax", config)
    assert is_valid is False
    assert env_var == "MINIMAX_API_KEY"


def test_config_key_takes_priority_over_os_env(monkeypatch: object) -> None:
    """Config key is preferred over OS env."""
    import os

    monkeypatch.setattr(os, "environ", {"MINIMAX_API_KEY": "from-os"})  # type: ignore[attr-defined]
    config = {"env": {"MINIMAX_API_KEY": "from-config"}}
    is_valid, _ = validate_provider_api_key("minimax", config)
    assert is_valid is True
