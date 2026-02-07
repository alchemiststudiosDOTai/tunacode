"""Handler protocol and implementations for TunaCode logging."""

import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

import structlog
from rich.console import RenderableType

from tunacode.core.logging.levels import LogLevel
from tunacode.core.logging.records import LogRecord

_file_renderer = structlog.processors.JSONRenderer()

TuiWriteCallback = Callable[[RenderableType], None]

# Lifecycle log prefixes for semantic coloring
# These must match the prefixes used in lifecycle log calls throughout the codebase
LIFECYCLE_PREFIX_ITERATION = "--- Iteration"
LIFECYCLE_PREFIX_TOKENS = "Tokens:"
LIFECYCLE_PREFIX_TOOLS = "Tools:"
LIFECYCLE_PREFIX_NO_TOOLS = "No tool calls"
LIFECYCLE_PREFIX_STREAM = "Stream:"
LIFECYCLE_PREFIX_RESPONSE = "Response:"
LIFECYCLE_PREFIX_THOUGHT = "Thought:"
LIFECYCLE_PREFIX_TASK_COMPLETED = "Task completed"
LIFECYCLE_PREFIX_ERROR = "Error:"
LIFECYCLE_PREFIX_RETRY = "Retry:"
LIFECYCLE_PREFIX_FALLBACK = "Fallback"

# Table-driven lifecycle formatting: (prefix, prefix_style, body_style)
_LIFECYCLE_SPLIT_STYLES: list[tuple[str, str, str]] = [
    (LIFECYCLE_PREFIX_TOKENS, "cyan bold", "cyan"),
    (LIFECYCLE_PREFIX_TOOLS, "green bold", "green"),
    (LIFECYCLE_PREFIX_STREAM, "blue bold", "blue"),
    (LIFECYCLE_PREFIX_RESPONSE, "yellow bold", "yellow"),
    (LIFECYCLE_PREFIX_THOUGHT, "magenta bold", "magenta italic"),
    (LIFECYCLE_PREFIX_ERROR, "red bold", "red"),
    (LIFECYCLE_PREFIX_RETRY, "yellow bold", "yellow"),
]

# Full-style lifecycle entries: (prefix, style)
_LIFECYCLE_FULL_STYLES: list[tuple[str, str]] = [
    (LIFECYCLE_PREFIX_ITERATION, "bold white"),
    (LIFECYCLE_PREFIX_NO_TOOLS, "dim"),
    (LIFECYCLE_PREFIX_TASK_COMPLETED, "green bold"),
    (LIFECYCLE_PREFIX_FALLBACK, "yellow dim"),
]


class Handler(ABC):
    """Base handler protocol for log output destinations."""

    def __init__(self, min_level: LogLevel = LogLevel.DEBUG):
        self.min_level = min_level
        self._enabled = True

    @abstractmethod
    def emit(self, record: LogRecord) -> None:
        """Write a log record to the destination."""

    def should_handle(self, record: LogRecord) -> bool:
        """Check if this handler should process the record."""
        return self._enabled and record.level >= self.min_level

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False


class FileHandler(Handler):
    """Handler that writes logs to a rotating file.

    Writes to ~/.local/share/tunacode/logs/tunacode.log with rotation.
    """

    MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
    BACKUP_COUNT = 5

    def __init__(
        self,
        log_path: Path | None = None,
        min_level: LogLevel = LogLevel.DEBUG,
    ):
        super().__init__(min_level)
        self._log_path = log_path or self._default_log_path()
        self._ensure_log_dir()

    def _default_log_path(self) -> Path:
        """Get XDG-compliant log path."""
        xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        return Path(xdg_data) / "tunacode" / "logs" / "tunacode.log"

    def _ensure_log_dir(self) -> None:
        self._log_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    @property
    def log_path(self) -> Path:
        return self._log_path

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size."""
        if not self._log_path.exists():
            return
        if self._log_path.stat().st_size < self.MAX_SIZE_BYTES:
            return

        # Rotate existing backups
        for i in range(self.BACKUP_COUNT - 1, 0, -1):
            old = self._log_path.with_suffix(f".log.{i}")
            new = self._log_path.with_suffix(f".log.{i + 1}")
            if old.exists():
                old.rename(new)

        # Current -> .log.1
        self._log_path.rename(self._log_path.with_suffix(".log.1"))

    def emit(self, record: LogRecord) -> None:
        if not self.should_handle(record):
            return

        self._rotate_if_needed()

        line = self._format_record(record)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _format_record(self, record: LogRecord) -> str:
        """Format record as JSON via structlog."""
        event_dict = record.to_dict()
        return _file_renderer(None, None, event_dict)


class TUIHandler(Handler):
    """Handler that pipes logs to RichLog when debug_mode is ON.

    Only active when debug_mode=True in SessionState.
    Uses a callback to write to the TUI without importing ui layer.
    """

    def __init__(
        self,
        write_callback: TuiWriteCallback | None = None,
        min_level: LogLevel = LogLevel.DEBUG,
    ):
        super().__init__(min_level)
        self._write_callback = write_callback

    def set_write_callback(self, callback: TuiWriteCallback) -> None:
        """Set the callback for writing to TUI (injected from app)."""
        self._write_callback = callback

    def emit(self, record: LogRecord) -> None:
        if not self.should_handle(record):
            return
        if self._write_callback is None:
            return

        text = self._format_record(record)
        self._write_callback(text)

    def _format_record(self, record: LogRecord) -> RenderableType:
        """Format record as Rich Text with styling based on content type."""
        from rich.text import Text

        msg = record.message

        # Detect lifecycle log type from message content and apply colors
        if msg.startswith("[LIFECYCLE]"):
            return self._format_lifecycle_record(msg[11:].strip())

        # Standard level-based styling
        style_map = {
            LogLevel.DEBUG: "dim",
            LogLevel.INFO: "",
            LogLevel.WARNING: "yellow",
            LogLevel.ERROR: "red bold",
            LogLevel.THOUGHT: "cyan italic",
            LogLevel.TOOL: "green",
        }

        style = style_map.get(record.level, "")
        prefix = f"[{record.level.name}]"

        text = Text()
        text.append(prefix, style="bold " + style)
        text.append(" ")
        text.append(record.message, style=style)

        if record.tool_name:
            text.append(f" ({record.tool_name})", style="dim")
        if record.duration_ms:
            text.append(f" [{record.duration_ms:.0f}ms]", style="dim")

        return text

    def _format_lifecycle_record(self, msg: str) -> RenderableType:
        """Format lifecycle logs with semantic colors."""
        from rich.text import Text

        text = Text()

        for prefix, prefix_style, body_style in _LIFECYCLE_SPLIT_STYLES:
            if msg.startswith(prefix):
                text.append(prefix + " ", style=prefix_style)
                text.append(msg[len(prefix) :], style=body_style)
                return text

        for prefix, style in _LIFECYCLE_FULL_STYLES:
            if msg.startswith(prefix):
                text.append(msg, style=style)
                return text

        # Iteration complete - dim
        if msg.startswith("Iteration") and "complete" in msg:
            text.append(msg, style="dim")
            return text

        # Default - dim for other lifecycle logs
        text.append(msg, style="dim")
        return text
