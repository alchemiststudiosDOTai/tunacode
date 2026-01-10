"""LogManager singleton for unified logging across TunaCode."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from tunacode.core.logging.handlers import FileHandler, Handler, TUIHandler
from tunacode.core.logging.levels import LogLevel
from tunacode.core.logging.records import LogRecord

if TYPE_CHECKING:
    from tunacode.core.state import StateManager


class LogManager:
    """Singleton manager for all logging operations.

    Thread-safe singleton that routes log records to registered handlers.
    File handler is always active; TUI handler only when debug_mode=True.
    """

    _instance: LogManager | None = None
    _instance_lock = threading.RLock()

    def __init__(self) -> None:
        self._handlers: list[Handler] = []
        self._state_manager: StateManager | None = None
        self._lock = threading.RLock()

        # Always register file handler
        self._file_handler = FileHandler()
        self._handlers.append(self._file_handler)

        # TUI handler (disabled until debug_mode)
        self._tui_handler = TUIHandler()
        self._tui_handler.disable()
        self._handlers.append(self._tui_handler)

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
            cls._instance = None

    def set_state_manager(self, state_manager: StateManager) -> None:
        """Bind state manager for debug_mode checking."""
        self._state_manager = state_manager

    def set_tui_callback(self, callback: Any) -> None:
        """Set the TUI write callback (called from app initialization)."""
        self._tui_handler.set_write_callback(callback)

    def set_debug_mode(self, enabled: bool) -> None:
        """Enable/disable debug mode (TUI output)."""
        if enabled:
            self._tui_handler.enable()
        else:
            self._tui_handler.disable()

    @property
    def debug_mode(self) -> bool:
        """Check current debug mode state."""
        if self._state_manager is None:
            return False
        return getattr(self._state_manager.session, "debug_mode", False)

    def log(self, record: LogRecord) -> None:
        """Route a log record to all handlers."""
        with self._lock:
            for handler in self._handlers:
                handler.emit(record)

    # Convenience methods
    def debug(self, message: str, **kwargs: Any) -> None:
        self.log(LogRecord(level=LogLevel.DEBUG, message=message, **kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        self.log(LogRecord(level=LogLevel.INFO, message=message, **kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        self.log(LogRecord(level=LogLevel.WARNING, message=message, **kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        self.log(LogRecord(level=LogLevel.ERROR, message=message, **kwargs))

    def thought(self, message: str, **kwargs: Any) -> None:
        self.log(LogRecord(level=LogLevel.THOUGHT, message=message, **kwargs))

    def tool(self, tool_name: str, message: str, **kwargs: Any) -> None:
        self.log(LogRecord(level=LogLevel.TOOL, message=message, tool_name=tool_name, **kwargs))


def get_logger() -> LogManager:
    """Get the global LogManager instance."""
    return LogManager.get_instance()
