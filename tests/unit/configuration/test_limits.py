"""Tests for tunacode.configuration.limits."""

from unittest.mock import patch

import pytest

from tunacode.configuration.limits import (
    _get_limit,
    clear_cache,
    get_command_limit,
    get_max_files_in_dir,
    get_max_tokens,
)
from tunacode.constants import MAX_COMMAND_OUTPUT, MAX_FILES_IN_DIR

LOAD_CONFIG_PATH = "tunacode.configuration.user_config.load_config"


@pytest.fixture(autouse=True)
def _clear_limits_cache() -> None:
    clear_cache()
    yield
    clear_cache()


class TestGetLimit:
    def test_returns_default_when_no_config(self):
        with patch(LOAD_CONFIG_PATH, return_value=None):
            clear_cache()
            assert _get_limit("max_command_output", 5000) == 5000

    def test_returns_setting_value_when_present(self):
        with patch(
            LOAD_CONFIG_PATH,
            return_value={"settings": {"max_command_output": 9999}},
        ):
            clear_cache()
            assert _get_limit("max_command_output", 5000) == 9999

    def test_returns_default_when_key_not_in_settings(self):
        with patch(
            LOAD_CONFIG_PATH,
            return_value={"settings": {"other_key": 1}},
        ):
            clear_cache()
            assert _get_limit("max_command_output", 5000) == 5000


class TestGetCommandLimit:
    def test_returns_default(self):
        with patch(LOAD_CONFIG_PATH, return_value=None):
            clear_cache()
            assert get_command_limit() == MAX_COMMAND_OUTPUT

    def test_returns_override(self):
        with patch(
            LOAD_CONFIG_PATH,
            return_value={"settings": {"max_command_output": 10000}},
        ):
            clear_cache()
            assert get_command_limit() == 10000


class TestGetMaxFilesInDir:
    def test_returns_default(self):
        with patch(LOAD_CONFIG_PATH, return_value=None):
            clear_cache()
            assert get_max_files_in_dir() == MAX_FILES_IN_DIR

    def test_returns_override(self):
        with patch(
            LOAD_CONFIG_PATH,
            return_value={"settings": {"max_files_in_dir": 200}},
        ):
            clear_cache()
            assert get_max_files_in_dir() == 200


class TestGetMaxTokens:
    def test_returns_none_by_default(self):
        with patch(LOAD_CONFIG_PATH, return_value=None):
            clear_cache()
            assert get_max_tokens() is None

    def test_returns_value_when_set(self):
        with patch(
            LOAD_CONFIG_PATH,
            return_value={"settings": {"max_tokens": 4096}},
        ):
            clear_cache()
            assert get_max_tokens() == 4096

    def test_returns_none_when_not_in_settings(self):
        with patch(
            LOAD_CONFIG_PATH,
            return_value={"settings": {"other": 1}},
        ):
            clear_cache()
            assert get_max_tokens() is None


class TestClearCache:
    def test_clear_allows_fresh_load(self):
        with patch(
            LOAD_CONFIG_PATH,
            return_value={"settings": {"max_command_output": 111}},
        ):
            clear_cache()
            assert get_command_limit() == 111

        with patch(
            LOAD_CONFIG_PATH,
            return_value={"settings": {"max_command_output": 222}},
        ):
            clear_cache()
            assert get_command_limit() == 222
