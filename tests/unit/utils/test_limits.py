"""Tests for the centralized limits module.

Tests cascading precedence: explicit setting > local_mode default > standard default.
"""

from unittest.mock import patch

import pytest

from tunacode.constants import (
    DEFAULT_READ_LIMIT,
    LOCAL_DEFAULT_READ_LIMIT,
    LOCAL_MAX_COMMAND_OUTPUT,
    LOCAL_MAX_FILES_IN_DIR,
    LOCAL_MAX_LINE_LENGTH,
    MAX_COMMAND_OUTPUT,
    MAX_FILES_IN_DIR,
    MAX_LINE_LENGTH,
)
from tunacode.utils.limits import (
    clear_cache,
    get_command_limit,
    get_max_files_in_dir,
    get_max_line_length,
    get_max_tokens,
    get_read_limit,
    is_local_mode,
)


@pytest.fixture(autouse=True)
def clear_limits_cache():
    """Clear cache before and after each test."""
    clear_cache()
    yield
    clear_cache()


class TestIsLocalMode:
    """Tests for is_local_mode()."""

    def test_returns_false_when_not_set(self):
        """Default is False when local_mode not in settings."""
        with patch("tunacode.utils.limits._load_settings", return_value={}):
            assert is_local_mode() is False

    def test_returns_true_when_enabled(self):
        """Returns True when local_mode is True."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"local_mode": True},
        ):
            assert is_local_mode() is True

    def test_returns_false_when_disabled(self):
        """Returns False when local_mode is explicitly False."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"local_mode": False},
        ):
            assert is_local_mode() is False


class TestGetReadLimit:
    """Tests for get_read_limit()."""

    def test_returns_standard_default(self):
        """Returns standard default when no settings."""
        with patch("tunacode.utils.limits._load_settings", return_value={}):
            assert get_read_limit() == DEFAULT_READ_LIMIT

    def test_returns_local_default_in_local_mode(self):
        """Returns local default when local_mode enabled."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"local_mode": True},
        ):
            assert get_read_limit() == LOCAL_DEFAULT_READ_LIMIT

    def test_explicit_setting_overrides_standard(self):
        """Explicit setting wins over standard default."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"read_limit": 500},
        ):
            assert get_read_limit() == 500

    def test_explicit_setting_overrides_local_mode(self):
        """Explicit setting wins even in local_mode."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"local_mode": True, "read_limit": 300},
        ):
            assert get_read_limit() == 300


class TestGetMaxLineLength:
    """Tests for get_max_line_length()."""

    def test_returns_standard_default(self):
        """Returns standard default when no settings."""
        with patch("tunacode.utils.limits._load_settings", return_value={}):
            assert get_max_line_length() == MAX_LINE_LENGTH

    def test_returns_local_default_in_local_mode(self):
        """Returns local default when local_mode enabled."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"local_mode": True},
        ):
            assert get_max_line_length() == LOCAL_MAX_LINE_LENGTH

    def test_explicit_setting_overrides(self):
        """Explicit setting wins."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"max_line_length": 1000},
        ):
            assert get_max_line_length() == 1000


class TestGetCommandLimit:
    """Tests for get_command_limit()."""

    def test_returns_standard_default(self):
        """Returns standard default when no settings."""
        with patch("tunacode.utils.limits._load_settings", return_value={}):
            assert get_command_limit() == MAX_COMMAND_OUTPUT

    def test_returns_local_default_in_local_mode(self):
        """Returns local default when local_mode enabled."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"local_mode": True},
        ):
            assert get_command_limit() == LOCAL_MAX_COMMAND_OUTPUT

    def test_explicit_setting_overrides(self):
        """Explicit setting wins."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"max_command_output": 2000},
        ):
            assert get_command_limit() == 2000


class TestGetMaxFilesInDir:
    """Tests for get_max_files_in_dir()."""

    def test_returns_standard_default(self):
        """Returns standard default when no settings."""
        with patch("tunacode.utils.limits._load_settings", return_value={}):
            assert get_max_files_in_dir() == MAX_FILES_IN_DIR

    def test_returns_local_default_in_local_mode(self):
        """Returns local default when local_mode enabled."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"local_mode": True},
        ):
            assert get_max_files_in_dir() == LOCAL_MAX_FILES_IN_DIR

    def test_explicit_setting_overrides(self):
        """Explicit setting wins."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"max_files_in_dir": 100},
        ):
            assert get_max_files_in_dir() == 100


class TestGetMaxTokens:
    """Tests for get_max_tokens()."""

    def test_returns_none_when_not_set(self):
        """Returns None when no limit configured."""
        with patch("tunacode.utils.limits._load_settings", return_value={}):
            assert get_max_tokens() is None

    def test_returns_local_default_in_local_mode(self):
        """Returns 1000 by default in local_mode."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"local_mode": True},
        ):
            assert get_max_tokens() == 1000

    def test_returns_custom_local_max_tokens(self):
        """Returns custom local_max_tokens in local_mode."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"local_mode": True, "local_max_tokens": 2000},
        ):
            assert get_max_tokens() == 2000

    def test_explicit_max_tokens_overrides(self):
        """Explicit max_tokens wins over local_mode."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"local_mode": True, "max_tokens": 500},
        ):
            assert get_max_tokens() == 500

    def test_explicit_max_tokens_without_local_mode(self):
        """Can set max_tokens without local_mode."""
        with patch(
            "tunacode.utils.limits._load_settings",
            return_value={"max_tokens": 4000},
        ):
            assert get_max_tokens() == 4000


class TestClearCache:
    """Tests for clear_cache()."""

    def test_cache_is_cleared(self):
        """Clearing cache allows settings to be reloaded."""
        call_count = 0

        def mock_load_config():
            nonlocal call_count
            call_count += 1
            return {"settings": {"local_mode": call_count > 1}}

        with patch(
            "tunacode.utils.config.user_configuration.load_config",
            side_effect=mock_load_config,
        ):
            clear_cache()

            # First call loads settings
            result1 = is_local_mode()
            assert result1 is False
            assert call_count == 1

            # Cached - no new call
            result2 = is_local_mode()
            assert result2 is False
            assert call_count == 1

            # Clear and reload
            clear_cache()
            result3 = is_local_mode()
            assert result3 is True
            assert call_count == 2
