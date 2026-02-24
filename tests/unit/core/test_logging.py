"""Tests for the core logging module.

Tests LogManager singleton, handlers, log levels, and redaction.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tunacode.core.logging import (
    FileHandler,
    LogLevel,
    LogManager,
    RedactingFilter,
    TUIHandler,
    get_logger,
)
from tunacode.core.logging.redaction import (
    REDACTED_PLACEHOLDER,
    TUNACODE_EXTRA_ATTR,
    is_sensitive_field,
    redact_dict,
    redact_message,
)
from tunacode.core.session import StateManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    level: int = logging.INFO,
    msg: str = "test",
    **extra: object,
) -> logging.LogRecord:
    """Create a stdlib LogRecord with optional tunacode_extra."""
    record = logging.LogRecord(
        name="tunacode",
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=None,
        exc_info=None,
    )
    record.tunacode_extra = extra  # type: ignore[attr-defined]
    return record


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_log_manager():
    """Reset LogManager singleton before and after each test."""
    LogManager.reset_instance()
    yield
    LogManager.reset_instance()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestLogManagerSingleton:
    """Tests for LogManager singleton behavior."""

    def test_get_instance_returns_same_instance(self):
        """get_logger() returns same instance on repeated calls."""
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2

    def test_get_instance_class_method_same_as_get_logger(self):
        """LogManager.get_instance() returns same as get_logger()."""
        instance = LogManager.get_instance()
        logger = get_logger()
        assert instance is logger

    def test_reset_instance_creates_new_instance(self):
        """reset_instance() allows creating a new singleton."""
        logger1 = get_logger()
        LogManager.reset_instance()
        logger2 = get_logger()
        assert logger1 is not logger2


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


class TestHandlerRegistration:
    """Tests for handler registration on the stdlib logger."""

    def test_file_handler_always_registered(self):
        """FileHandler is registered by default."""
        logger = get_logger()
        file_handlers = [h for h in logger._logger.handlers if isinstance(h, FileHandler)]
        assert len(file_handlers) == 1

    def test_tui_handler_registered_but_disabled(self):
        """TUIHandler is registered but disabled by default."""
        logger = get_logger()
        tui_handlers = [h for h in logger._logger.handlers if isinstance(h, TUIHandler)]
        assert len(tui_handlers) == 1
        assert tui_handlers[0]._enabled is False

    def test_tui_handler_enabled_in_debug_mode(self):
        """TUIHandler is enabled when debug_mode=True."""
        logger = get_logger()
        logger.set_debug_mode(True)

        tui_handlers = [h for h in logger._logger.handlers if isinstance(h, TUIHandler)]
        assert tui_handlers[0]._enabled is True

    def test_tui_handler_disabled_when_debug_mode_off(self):
        """TUIHandler is disabled when debug_mode=False."""
        logger = get_logger()
        logger.set_debug_mode(True)
        logger.set_debug_mode(False)

        tui_handlers = [h for h in logger._logger.handlers if isinstance(h, TUIHandler)]
        assert tui_handlers[0]._enabled is False

    def test_redacting_filter_registered(self):
        """A RedactingFilter is attached to the stdlib logger."""
        logger = get_logger()
        redacting_filters = [f for f in logger._logger.filters if isinstance(f, RedactingFilter)]
        assert len(redacting_filters) == 1


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestLogManagerProperties:
    """Tests for LogManager properties."""

    def test_log_path_matches_file_handler(self):
        """log_path returns the FileHandler's path."""
        logger = get_logger()
        file_handlers = [h for h in logger._logger.handlers if isinstance(h, FileHandler)]
        assert logger.log_path == file_handlers[0].log_path


# ---------------------------------------------------------------------------
# Log levels
# ---------------------------------------------------------------------------


class TestLogLevels:
    """Tests for LogLevel enum."""

    def test_log_level_ordering(self):
        """DEBUG < INFO < WARNING < ERROR < THOUGHT < TOOL."""
        assert LogLevel.DEBUG < LogLevel.INFO
        assert LogLevel.INFO < LogLevel.WARNING
        assert LogLevel.WARNING < LogLevel.ERROR
        assert LogLevel.ERROR < LogLevel.THOUGHT
        assert LogLevel.THOUGHT < LogLevel.TOOL

    def test_log_level_values(self):
        """Log levels match stdlib for standard levels."""
        assert LogLevel.DEBUG == 10
        assert LogLevel.INFO == 20
        assert LogLevel.WARNING == 30
        assert LogLevel.ERROR == 40
        assert LogLevel.THOUGHT == 45
        assert LogLevel.TOOL == 46

    def test_custom_levels_registered_with_stdlib(self):
        """Custom levels are registered with logging.getLevelName()."""
        assert logging.getLevelName(45) == "THOUGHT"
        assert logging.getLevelName(46) == "TOOL"


# ---------------------------------------------------------------------------
# FileHandler
# ---------------------------------------------------------------------------


class TestFileHandler:
    """Tests for FileHandler configuration."""

    def test_file_handler_rotation_config(self):
        """FileHandler configured for 10MB/5 backups."""
        assert FileHandler.MAX_SIZE_BYTES == 10 * 1024 * 1024
        assert FileHandler.BACKUP_COUNT == 5

    def test_file_handler_xdg_path(self):
        """FileHandler uses XDG-compliant path by default."""
        handler = FileHandler()
        expected_suffix = Path("tunacode") / "logs" / "tunacode.log"
        assert str(handler._log_path).endswith(str(expected_suffix))

    def test_file_handler_custom_path(self):
        """FileHandler accepts custom log path."""
        custom_path = Path("/tmp/test.log")
        handler = FileHandler(log_path=custom_path)
        assert handler._log_path == custom_path

    def test_file_handler_is_stdlib_rotating_handler(self):
        """FileHandler is a subclass of stdlib RotatingFileHandler."""
        assert issubclass(FileHandler, logging.handlers.RotatingFileHandler)


# ---------------------------------------------------------------------------
# Convenience methods
# ---------------------------------------------------------------------------


class TestConvenienceMethods:
    """Tests for LogManager convenience methods."""

    def test_debug_emits_debug_level(self):
        """debug() emits a DEBUG-level record."""
        logger = get_logger()
        with patch.object(logger._logger, "log") as mock_log:
            logger.debug("test message")
            mock_log.assert_called_once()
            level_arg = mock_log.call_args[0][0]
            msg_arg = mock_log.call_args[0][1]
            assert level_arg == LogLevel.DEBUG
            assert msg_arg == "test message"

    def test_info_emits_info_level(self):
        """info() emits an INFO-level record."""
        logger = get_logger()
        with patch.object(logger._logger, "log") as mock_log:
            logger.info("test message")
            level_arg = mock_log.call_args[0][0]
            assert level_arg == LogLevel.INFO

    def test_warning_emits_warning_level(self):
        """warning() emits a WARNING-level record."""
        logger = get_logger()
        with patch.object(logger._logger, "log") as mock_log:
            logger.warning("test message")
            level_arg = mock_log.call_args[0][0]
            assert level_arg == LogLevel.WARNING

    def test_error_emits_error_level(self):
        """error() emits an ERROR-level record."""
        logger = get_logger()
        with patch.object(logger._logger, "log") as mock_log:
            logger.error("test message")
            level_arg = mock_log.call_args[0][0]
            assert level_arg == LogLevel.ERROR

    def test_thought_emits_thought_level(self):
        """thought() emits a THOUGHT-level record."""
        logger = get_logger()
        with patch.object(logger._logger, "log") as mock_log:
            logger.thought("test message")
            level_arg = mock_log.call_args[0][0]
            assert level_arg == LogLevel.THOUGHT

    def test_tool_emits_tool_level_with_name(self):
        """tool() emits a TOOL-level record with tool_name in extra."""
        logger = get_logger()
        with patch.object(logger._logger, "log") as mock_log:
            logger.tool("bash", "completed", duration_ms=100.0)
            level_arg = mock_log.call_args[0][0]
            assert level_arg == LogLevel.TOOL
            extra = mock_log.call_args[1]["extra"][TUNACODE_EXTRA_ATTR]
            assert extra["tool_name"] == "bash"
            assert extra["duration_ms"] == 100.0

    def test_lifecycle_gated_by_debug_mode(self):
        """lifecycle() only logs when debug_mode=True."""
        logger = get_logger()
        state_manager = StateManager()
        logger.set_state_manager(state_manager)

        with patch.object(logger._logger, "log") as mock_log:
            logger.lifecycle("test message")
            mock_log.assert_not_called()

        state_manager.session.debug_mode = True
        with patch.object(logger._logger, "log") as mock_log:
            logger.lifecycle("test message")
            mock_log.assert_called_once()
            msg_arg = mock_log.call_args[0][1]
            assert msg_arg.startswith("[LIFECYCLE]")

    def test_extra_kwarg_flattened(self):
        """Nested ``extra`` dict is merged into tunacode_extra."""
        logger = get_logger()
        with patch.object(logger._logger, "log") as mock_log:
            logger.info("msg", request_id="abc", extra={"count": 5})
            extra = mock_log.call_args[1]["extra"][TUNACODE_EXTRA_ATTR]
            assert extra["request_id"] == "abc"
            assert extra["count"] == 5
            assert "extra" not in extra


# ---------------------------------------------------------------------------
# TUIHandler
# ---------------------------------------------------------------------------


class TestTUIHandler:
    """Tests for TUIHandler."""

    def test_tui_handler_requires_callback(self):
        """TUIHandler does nothing without callback set."""
        handler = TUIHandler()
        handler.enable()
        record = _make_record()
        handler.emit(record)

    def test_tui_handler_calls_callback(self):
        """TUIHandler calls write_callback when enabled."""
        mock_callback = MagicMock()
        handler = TUIHandler(write_callback=mock_callback)
        handler.enable()

        record = _make_record()
        handler.emit(record)

        mock_callback.assert_called_once()

    def test_tui_handler_respects_min_level(self):
        """TUIHandler respects min_level setting."""
        mock_callback = MagicMock()
        handler = TUIHandler(write_callback=mock_callback, min_level=LogLevel.WARNING)
        handler.enable()

        debug_record = _make_record(level=logging.DEBUG, msg="debug")
        handler.emit(debug_record)
        mock_callback.assert_not_called()

        warn_record = _make_record(level=logging.WARNING, msg="warning")
        handler.emit(warn_record)
        mock_callback.assert_called_once()


# ---------------------------------------------------------------------------
# Redaction — unit tests
# ---------------------------------------------------------------------------


class TestRedactMessage:
    """Tests for regex-based message redaction."""

    def test_redacts_api_key(self):
        """API keys (sk-...) are replaced."""
        msg = "Using key sk-abc123def456ghi789jkl012"
        result = redact_message(msg)
        assert "sk-abc123" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_redacts_bearer_token(self):
        """Bearer tokens are replaced."""
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5c"
        result = redact_message(msg)
        assert "eyJhbGci" not in result
        assert f"Bearer {REDACTED_PLACEHOLDER}" in result

    def test_redacts_email(self):
        """Email addresses are replaced."""
        msg = "Contact user@example.com for details"
        result = redact_message(msg)
        assert "user@example.com" not in result
        assert REDACTED_PLACEHOLDER in result

    def test_preserves_non_sensitive_message(self):
        """Non-sensitive messages are unchanged."""
        msg = "Request completed in 150ms"
        assert redact_message(msg) == msg


class TestRedactDict:
    """Tests for field-name-based dict redaction."""

    def test_redacts_password_field(self):
        """Fields containing 'password' are redacted."""
        data = {"user_password": "hunter2", "username": "alice"}
        result = redact_dict(data)
        assert result["user_password"] == REDACTED_PLACEHOLDER
        assert result["username"] == "alice"

    def test_redacts_token_field(self):
        """Fields containing 'token' are redacted."""
        data = {"auth_token": "abc123", "count": 5}
        result = redact_dict(data)
        assert result["auth_token"] == REDACTED_PLACEHOLDER
        assert result["count"] == 5

    def test_redacts_api_key_field(self):
        """Fields containing 'api_key' are redacted."""
        data = {"api_key": "sk-secret123"}
        assert redact_dict(data)["api_key"] == REDACTED_PLACEHOLDER

    def test_redacts_nested_dicts(self):
        """Nested dicts are recursively redacted."""
        data = {"config": {"secret": "hidden", "name": "test"}}
        result = redact_dict(data)
        assert result["config"]["secret"] == REDACTED_PLACEHOLDER
        assert result["config"]["name"] == "test"

    def test_redacts_string_values_with_patterns(self):
        """String values are scrubbed with regex patterns."""
        data = {"log_line": "key is sk-abc123def456ghi789jkl012"}
        result = redact_dict(data)
        assert "sk-abc123" not in result["log_line"]


class TestIsSensitiveField:
    """Tests for field-name sensitivity detection."""

    def test_known_sensitive_fields(self):
        assert is_sensitive_field("password") is True
        assert is_sensitive_field("API_KEY") is True
        assert is_sensitive_field("user_token") is True
        assert is_sensitive_field("my_secret") is True
        assert is_sensitive_field("authorization") is True

    def test_non_sensitive_fields(self):
        assert is_sensitive_field("username") is False
        assert is_sensitive_field("request_id") is False
        assert is_sensitive_field("iteration") is False


class TestRedactingFilter:
    """Tests for the stdlib logging filter."""

    def test_filter_redacts_msg(self):
        """RedactingFilter scrubs sensitive data from record.msg."""
        filt = RedactingFilter()
        record = _make_record(msg="key=sk-abc123def456ghi789jkl012")
        filt.filter(record)
        assert "sk-abc123" not in record.msg

    def test_filter_redacts_tunacode_extra(self):
        """RedactingFilter scrubs sensitive keys in tunacode_extra."""
        filt = RedactingFilter()
        record = _make_record(api_key="supersecret")
        filt.filter(record)
        extra = getattr(record, TUNACODE_EXTRA_ATTR)
        assert extra["api_key"] == REDACTED_PLACEHOLDER

    def test_filter_always_returns_true(self):
        """RedactingFilter never suppresses records."""
        filt = RedactingFilter()
        record = _make_record()
        assert filt.filter(record) is True
