"""Handler protocol and implementations for TunaCode logging."""

import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tunacode.core.logging.levels import LogLevel
from tunacode.core.logging.records import LogRecord

if TYPE_CHECKING:
    from rich.console import RenderableType

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
        """Format record as structured log line."""
        ts = record.timestamp.isoformat()
        level = record.level.name.ljust(7)
        parts = [f"{ts} [{level}]"]

        if record.source:
            parts.append(f"[{record.source}]")
        if record.request_id:
            parts.append(f"req={record.request_id}")
        if record.iteration:
            parts.append(f"iter={record.iteration}")
        if record.tool_name:
            parts.append(f"tool={record.tool_name}")
        if record.duration_ms:
            parts.append(f"dur={record.duration_ms:.1f}ms")

        parts.append(record.message)
        return " ".join(parts)


class TUIHandler(Handler):
    """Handler that pipes logs to RichLog when debug_mode is ON.

    Only active when debug_mode=True in SessionState.
    Uses a callback to write to the TUI without importing ui layer.
    """

    def __init__(
        self,
        write_callback: Callable[["RenderableType"], Any] | None = None,
        min_level: LogLevel = LogLevel.DEBUG,
    ):
        super().__init__(min_level)
        self._write_callback = write_callback

    def set_write_callback(self, callback: Callable[["RenderableType"], Any]) -> None:
        """Set the callback for writing to TUI (injected from app)."""
        self._write_callback = callback

    def emit(self, record: LogRecord) -> None:
        if not self.should_handle(record):
            return
        if self._write_callback is None:
            return

        text = self._format_record(record)
        self._write_callback(text)

    def _format_record(self, record: LogRecord) -> "RenderableType":
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

    def _format_lifecycle_record(self, msg: str) -> "RenderableType":
        """Format lifecycle logs with semantic colors."""
        from rich.text import Text

        text = Text()

        # Iteration header - bold white
        if msg.startswith(LIFECYCLE_PREFIX_ITERATION):
            text.append(msg, style="bold white")
            return text

        # Tokens - cyan for metrics
        if msg.startswith(LIFECYCLE_PREFIX_TOKENS):
            prefix_len = len(LIFECYCLE_PREFIX_TOKENS)
            text.append(LIFECYCLE_PREFIX_TOKENS + " ", style="cyan bold")
            text.append(msg[prefix_len:], style="cyan")
            return text

        # Tools - green for tool activity
        if msg.startswith(LIFECYCLE_PREFIX_TOOLS):
            prefix_len = len(LIFECYCLE_PREFIX_TOOLS)
            text.append(LIFECYCLE_PREFIX_TOOLS + " ", style="green bold")
            text.append(msg[prefix_len:], style="green")
            return text

        if msg.startswith(LIFECYCLE_PREFIX_NO_TOOLS):
            text.append(msg, style="dim")
            return text

        # Stream - blue for streaming info
        if msg.startswith(LIFECYCLE_PREFIX_STREAM):
            prefix_len = len(LIFECYCLE_PREFIX_STREAM)
            text.append(LIFECYCLE_PREFIX_STREAM + " ", style="blue bold")
            text.append(msg[prefix_len:], style="blue")
            return text

        # Response - yellow for model output
        if msg.startswith(LIFECYCLE_PREFIX_RESPONSE):
            prefix_len = len(LIFECYCLE_PREFIX_RESPONSE)
            text.append(LIFECYCLE_PREFIX_RESPONSE + " ", style="yellow bold")
            text.append(msg[prefix_len:], style="yellow")
            return text

        # Thought - magenta/italic for thinking
        if msg.startswith(LIFECYCLE_PREFIX_THOUGHT):
            prefix_len = len(LIFECYCLE_PREFIX_THOUGHT)
            text.append(LIFECYCLE_PREFIX_THOUGHT + " ", style="magenta bold")
            text.append(msg[prefix_len:], style="magenta italic")
            return text

        # Iteration complete - dim
        if msg.startswith("Iteration") and "complete" in msg:
            text.append(msg, style="dim")
            return text

        # Task completed - bright green
        if msg.startswith(LIFECYCLE_PREFIX_TASK_COMPLETED):
            text.append(msg, style="green bold")
            return text

        # Errors - red bold
        if msg.startswith(LIFECYCLE_PREFIX_ERROR):
            prefix_len = len(LIFECYCLE_PREFIX_ERROR)
            text.append(LIFECYCLE_PREFIX_ERROR + " ", style="red bold")
            text.append(msg[prefix_len:], style="red")
            return text

        # Retries - yellow/orange warning
        if msg.startswith(LIFECYCLE_PREFIX_RETRY):
            prefix_len = len(LIFECYCLE_PREFIX_RETRY)
            text.append(LIFECYCLE_PREFIX_RETRY + " ", style="yellow bold")
            text.append(msg[prefix_len:], style="yellow")
            return text

        # Fallback parsing - dim yellow (indicates potential issue)
        if msg.startswith(LIFECYCLE_PREFIX_FALLBACK):
            text.append(msg, style="yellow dim")
            return text

        # Fallback - dim for other lifecycle logs
        text.append(msg, style="dim")
        return text
