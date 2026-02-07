"""Tests for tunacode.configuration.user_config."""

import json
from unittest.mock import patch

import pytest

from tunacode.configuration.user_config import (
    load_config,
    merge_user_config,
)
from tunacode.exceptions import ConfigurationError


class TestMergeUserConfig:
    def test_none_user_config_returns_defaults(self):
        defaults = {"default_model": "x", "settings": {"a": 1}}
        assert merge_user_config(defaults, None) == defaults

    def test_empty_user_config_returns_defaults(self):
        defaults = {"default_model": "x", "settings": {"a": 1}}
        assert merge_user_config(defaults, {}) == defaults

    def test_top_level_override(self):
        defaults = {"default_model": "x", "settings": {"a": 1}}
        user = {"default_model": "y"}
        result = merge_user_config(defaults, user)
        assert result["default_model"] == "y"

    def test_settings_merge(self):
        defaults = {"default_model": "x", "settings": {"a": 1, "b": 2}}
        user = {"settings": {"b": 99}}
        result = merge_user_config(defaults, user)
        assert result["settings"]["a"] == 1
        assert result["settings"]["b"] == 99

    def test_does_not_mutate_default(self):
        defaults = {"default_model": "x", "settings": {"a": 1}}
        user = {"default_model": "y", "settings": {"a": 2}}
        merge_user_config(defaults, user)
        assert defaults["default_model"] == "x"
        assert defaults["settings"]["a"] == 1

    def test_user_adds_new_top_level_key(self):
        defaults = {"default_model": "x", "settings": {"a": 1}}
        user = {"extra_key": "val"}
        result = merge_user_config(defaults, user)
        assert result["extra_key"] == "val"

    def test_user_adds_new_setting(self):
        defaults = {"default_model": "x", "settings": {"a": 1}}
        user = {"settings": {"b": 2}}
        result = merge_user_config(defaults, user)
        assert result["settings"]["b"] == 2
        assert result["settings"]["a"] == 1


class TestLoadConfig:
    def test_missing_file_returns_none(self, tmp_path):
        with patch("tunacode.configuration.user_config.ApplicationSettings") as mock_settings:
            mock_settings.return_value.paths.config_file = tmp_path / "nonexistent.json"
            result = load_config()
            assert result is None

    def test_valid_json_loads(self, tmp_path):
        config_file = tmp_path / "tunacode.json"
        config_data = {"default_model": "openai:gpt-4", "env": {}}
        config_file.write_text(json.dumps(config_data))

        with patch("tunacode.configuration.user_config.ApplicationSettings") as mock_settings:
            mock_settings.return_value.paths.config_file = config_file
            result = load_config()
            assert result == config_data

    def test_malformed_json_raises_configuration_error(self, tmp_path):
        config_file = tmp_path / "tunacode.json"
        config_file.write_text("{invalid json")

        with patch("tunacode.configuration.user_config.ApplicationSettings") as mock_settings:
            mock_settings.return_value.paths.config_file = config_file
            with pytest.raises(ConfigurationError, match="Invalid JSON"):
                load_config()

    def test_permission_error_raises_configuration_error(self, tmp_path):
        with patch("tunacode.configuration.user_config.ApplicationSettings") as mock_settings:
            mock_settings.return_value.paths.config_file = tmp_path / "tunacode.json"
            with (
                patch("builtins.open", side_effect=PermissionError("denied")),
                pytest.raises(ConfigurationError, match="Failed to load"),
            ):
                load_config()
