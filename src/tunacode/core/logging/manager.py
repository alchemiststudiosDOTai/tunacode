"""LogManager singleton for unified logging across TunaCode.

Wraps Python's stdlib ``logging`` module.  The singleton ``LogManager``
configures a named logger (``"tunacode"``) with:

- A ``RotatingFileHandler`` that is always active.
- A ``TUIHandler`` that is enabled only in debug mode.
- A ``RedactingFilter`` that scrubs sensitive data from every record.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from tunacode.core.logging.handlers import FileHandler, TUIHandler, TuiWriteCallback
from tunacode.core.logging.levels import THOUGHT_LEVEL, TOOL_LEVEL, LogLevel
from tunacode.core.logging.redaction import TUNACODE_EXTRA_ATTR, RedactingFilter
from tunacode.core.types import StateManagerProtocol

LIFECYCLE_PREFIX: str = "[LIFECYCLE]"
LOGGER_NAME: str = "tunacode"


class LogManager:
    """Singleton manager for all logging operations.

    Thread-safe singleton that wraps a stdlib ``logging.Logger`` and routes
    records to registered handlers.  File handler is always active; TUI
    handler only when ``debug_mode=True``.
    """

    _instance: LogManager | None = None
    _instance_lock = threading.RLock()

    def __init__(self) -> None:
        self._logger = logging.getLogger(LOGGER_NAME)
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        # Clear any leftover handlers/filters from previous instances (tests).
        self._logger.handlers.clear()
        self._logger.filters.clear()

        self._state_manager: StateManagerProtocol | None = None

        # Always register file handler
        self._file_handler = FileHandler()
        self._logger.addHandler(self._file_handler)

        # TUI handler (disabled until debug_mode)
        self._tui_handler = TUIHandler()
        self._logger.addHandler(self._tui_handler)

        # Redaction filter scrubs every record before handlers see it.
        self._logger.addFilter(RedactingFilter())

    @classmethod
    def get_instance(cls) -> LogManager:
        """Get the singleton LogManager instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance._logger.handlers.clear()
                cls._instance._logger.filters.clear()
            cls._instance = None

    def set_state_manager(self, state_manager: StateManagerProtocol) -> None:
        """Bind state manager for debug_mode checking."""
        self._state_manager = state_manager

    def set_tui_callback(self, callback: TuiWriteCallback) -> None:
        """Set the TUI write callback (called from app initialization)."""
        self._tui_handler.set_write_callback(callback)

    def set_debug_mode(self, enabled: bool) -> None:
        """Enable/disable debug mode (TUI output)."""
        if enabled:
            self._tui_handler.enable()
        else:
            self._tui_handler.disable()

    @property
    def log_path(self) -> Path:
        """Return the active file log path."""
        return self._file_handler.log_path

    @property
    def debug_mode(self) -> bool:
        """Check current debug mode state."""
        if self._state_manager is None:
            return False
        return getattr(self._state_manager.session, "debug_mode", False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten_extra(kwargs: dict[str, Any]) -> dict[str, Any]:
        """Merge caller kwargs and optional nested ``extra`` dict into one flat dict."""
        result = dict(kwargs)
        nested = result.pop("extra", None)
        if isinstance(nested, dict):
            result.update(nested)
        return result

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        """Emit a log record at *level* with structured extra data."""
        extra_data = self._flatten_extra(kwargs)
        self._logger.log(level, message, extra={TUNACODE_EXTRA_ATTR: extra_data})

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(LogLevel.ERROR, message, **kwargs)

    def thought(self, message: str, **kwargs: Any) -> None:
        self._log(THOUGHT_LEVEL, message, **kwargs)

    def tool(self, tool_name: str, message: str, **kwargs: Any) -> None:
        kwargs["tool_name"] = tool_name
        self._log(TOOL_LEVEL, message, **kwargs)

    def lifecycle(self, message: str, **kwargs: Any) -> None:
        """Emit lifecycle debug logs only when debug_mode is enabled."""
        if not self.debug_mode:
            return
        lifecycle_message = f"{LIFECYCLE_PREFIX} {message}"
        self._log(LogLevel.DEBUG, lifecycle_message, **kwargs)


def get_logger() -> LogManager:
    """Get the global LogManager instance."""
    return LogManager.get_instance()
