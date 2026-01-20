"""Tests for the core logging module.

Tests LogManager singleton, handlers, LogRecord, and log levels.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tunacode.core.logging import (
    FileHandler,
    LogLevel,
    LogManager,
    LogRecord,
    TUIHandler,
    get_logger,
)
from tunacode.core.state import StateManager


@pytest.fixture(autouse=True)
def reset_log_manager():
    """Reset LogManager singleton before and after each test."""
    LogManager.reset_instance()
    yield
    LogManager.reset_instance()


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


class TestHandlerRegistration:
    """Tests for handler registration."""

    def test_file_handler_always_registered(self):
        """FileHandler is registered by default."""
        logger = get_logger()
        file_handlers = [h for h in logger._handlers if isinstance(h, FileHandler)]
        assert len(file_handlers) == 1

    def test_tui_handler_registered_but_disabled(self):
        """TUIHandler is registered but disabled by default."""
        logger = get_logger()
        tui_handlers = [h for h in logger._handlers if isinstance(h, TUIHandler)]
        assert len(tui_handlers) == 1
        assert tui_handlers[0]._enabled is False

    def test_tui_handler_enabled_in_debug_mode(self):
        """TUIHandler is enabled when debug_mode=True."""
        logger = get_logger()
        logger.set_debug_mode(True)

        tui_handlers = [h for h in logger._handlers if isinstance(h, TUIHandler)]
        assert tui_handlers[0]._enabled is True

    def test_tui_handler_disabled_when_debug_mode_off(self):
        """TUIHandler is disabled when debug_mode=False."""
        logger = get_logger()
        logger.set_debug_mode(True)
        logger.set_debug_mode(False)

        tui_handlers = [h for h in logger._handlers if isinstance(h, TUIHandler)]
        assert tui_handlers[0]._enabled is False


class TestLogManagerProperties:
    """Tests for LogManager properties."""

    def test_log_path_matches_file_handler(self):
        """log_path returns the FileHandler's path."""
        logger = get_logger()
        file_handlers = [h for h in logger._handlers if isinstance(h, FileHandler)]
        assert logger.log_path == file_handlers[0].log_path


class TestLogRecord:
    """Tests for LogRecord dataclass."""

    def test_log_record_is_frozen(self):
        """LogRecord is immutable (frozen dataclass)."""
        record = LogRecord(level=LogLevel.INFO, message="test")
        with pytest.raises(FrozenInstanceError):
            record.message = "modified"

    def test_log_record_default_values(self):
        """LogRecord has sensible defaults."""
        record = LogRecord(level=LogLevel.INFO, message="test")

        assert record.level == LogLevel.INFO
        assert record.message == "test"
        assert isinstance(record.timestamp, datetime)
        assert record.source == ""
        assert record.request_id == ""
        assert record.iteration == 0
        assert record.tool_name == ""
        assert record.duration_ms == 0.0
        assert record.extra == {}

    def test_log_record_with_kwargs(self):
        """LogRecord accepts all metadata fields."""
        record = LogRecord(
            level=LogLevel.TOOL,
            message="completed",
            request_id="abc123",
            iteration=5,
            tool_name="bash",
            duration_ms=150.5,
        )

        assert record.request_id == "abc123"
        assert record.iteration == 5
        assert record.tool_name == "bash"
        assert record.duration_ms == 150.5

    def test_log_record_timestamp_is_utc(self):
        """LogRecord timestamp is UTC by default."""
        record = LogRecord(level=LogLevel.INFO, message="test")
        assert record.timestamp.tzinfo == UTC


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
        """Log levels have expected numeric values."""
        assert LogLevel.DEBUG == 10
        assert LogLevel.INFO == 20
        assert LogLevel.WARNING == 30
        assert LogLevel.ERROR == 40
        assert LogLevel.THOUGHT == 50
        assert LogLevel.TOOL == 60


class TestFileHandler:
    """Tests for FileHandler configuration."""

    def test_file_handler_rotation_config(self):
        """FileHandler configured for 10MB/5 backups."""
        assert FileHandler.MAX_SIZE_BYTES == 10 * 1024 * 1024  # 10MB
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


class TestConvenienceMethods:
    """Tests for LogManager convenience methods."""

    def test_debug_creates_debug_record(self):
        """debug() creates DEBUG level record."""
        logger = get_logger()
        with patch.object(logger, "log") as mock_log:
            logger.debug("test message")
            call_args = mock_log.call_args[0][0]
            assert call_args.level == LogLevel.DEBUG
            assert call_args.message == "test message"

    def test_info_creates_info_record(self):
        """info() creates INFO level record."""
        logger = get_logger()
        with patch.object(logger, "log") as mock_log:
            logger.info("test message")
            call_args = mock_log.call_args[0][0]
            assert call_args.level == LogLevel.INFO

    def test_warning_creates_warning_record(self):
        """warning() creates WARNING level record."""
        logger = get_logger()
        with patch.object(logger, "log") as mock_log:
            logger.warning("test message")
            call_args = mock_log.call_args[0][0]
            assert call_args.level == LogLevel.WARNING

    def test_error_creates_error_record(self):
        """error() creates ERROR level record."""
        logger = get_logger()
        with patch.object(logger, "log") as mock_log:
            logger.error("test message")
            call_args = mock_log.call_args[0][0]
            assert call_args.level == LogLevel.ERROR

    def test_thought_creates_thought_record(self):
        """thought() creates THOUGHT level record."""
        logger = get_logger()
        with patch.object(logger, "log") as mock_log:
            logger.thought("test message")
            call_args = mock_log.call_args[0][0]
            assert call_args.level == LogLevel.THOUGHT

    def test_tool_creates_tool_record_with_name(self):
        """tool() creates TOOL level record with tool_name."""
        logger = get_logger()
        with patch.object(logger, "log") as mock_log:
            logger.tool("bash", "completed", duration_ms=100.0)
            call_args = mock_log.call_args[0][0]
            assert call_args.level == LogLevel.TOOL
            assert call_args.tool_name == "bash"
            assert call_args.message == "completed"
            assert call_args.duration_ms == 100.0

    def test_lifecycle_gated_by_debug_mode(self):
        """lifecycle() only logs when debug_mode=True."""
        logger = get_logger()
        state_manager = StateManager()
        logger.set_state_manager(state_manager)

        with patch.object(logger, "log") as mock_log:
            logger.lifecycle("test message")
            mock_log.assert_not_called()

        state_manager.session.debug_mode = True
        with patch.object(logger, "log") as mock_log:
            logger.lifecycle("test message")
            call_args = mock_log.call_args[0][0]
            assert call_args.level == LogLevel.DEBUG
            assert call_args.message.startswith("[LIFECYCLE]")


class TestTUIHandler:
    """Tests for TUIHandler."""

    def test_tui_handler_requires_callback(self):
        """TUIHandler does nothing without callback set."""
        handler = TUIHandler()
        handler.enable()
        record = LogRecord(level=LogLevel.INFO, message="test")
        # Should not raise, just do nothing
        handler.emit(record)

    def test_tui_handler_calls_callback(self):
        """TUIHandler calls write_callback when enabled."""
        mock_callback = MagicMock()
        handler = TUIHandler(write_callback=mock_callback)
        handler.enable()

        record = LogRecord(level=LogLevel.INFO, message="test")
        handler.emit(record)

        mock_callback.assert_called_once()

    def test_tui_handler_respects_min_level(self):
        """TUIHandler respects min_level setting."""
        mock_callback = MagicMock()
        handler = TUIHandler(write_callback=mock_callback, min_level=LogLevel.WARNING)
        handler.enable()

        # DEBUG should be filtered
        debug_record = LogRecord(level=LogLevel.DEBUG, message="debug")
        handler.emit(debug_record)
        mock_callback.assert_not_called()

        # WARNING should pass
        warn_record = LogRecord(level=LogLevel.WARNING, message="warning")
        handler.emit(warn_record)
        mock_callback.assert_called_once()
