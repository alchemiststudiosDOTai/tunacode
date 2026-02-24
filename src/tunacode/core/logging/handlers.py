"""Handler implementations for TunaCode logging.

Provides stdlib ``logging.Handler`` subclasses:
- ``FileHandler``: rotating file handler with structured formatting.
- ``TUIHandler``: Rich-formatted handler for debug TUI output.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from rich.console import RenderableType

from tunacode.core.logging.levels import LogLevel
from tunacode.core.logging.redaction import TUNACODE_EXTRA_ATTR

TuiWriteCallback = Callable[[RenderableType], None]

# ---------------------------------------------------------------------------
# Lifecycle log prefixes for semantic coloring
# ---------------------------------------------------------------------------

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
LIFECYCLE_PREFIX_USAGE = "Usage:"
LIFECYCLE_PREFIX_RESOURCE = "Resource:"

# Table-driven lifecycle formatting: (prefix, prefix_style, body_style)
_LIFECYCLE_SPLIT_STYLES: list[tuple[str, str, str]] = [
    (LIFECYCLE_PREFIX_TOKENS, "cyan bold", "cyan"),
    (LIFECYCLE_PREFIX_TOOLS, "green bold", "green"),
    (LIFECYCLE_PREFIX_STREAM, "blue bold", "blue"),
    (LIFECYCLE_PREFIX_RESPONSE, "yellow bold", "yellow"),
    (LIFECYCLE_PREFIX_THOUGHT, "magenta bold", "magenta italic"),
    (LIFECYCLE_PREFIX_ERROR, "red bold", "red"),
    (LIFECYCLE_PREFIX_RETRY, "yellow bold", "yellow"),
    (LIFECYCLE_PREFIX_USAGE, "cyan bold", "cyan"),
    (LIFECYCLE_PREFIX_RESOURCE, "blue bold", "blue"),
]

# Full-style lifecycle entries: (prefix, style)
_LIFECYCLE_FULL_STYLES: list[tuple[str, str]] = [
    (LIFECYCLE_PREFIX_ITERATION, "bold white"),
    (LIFECYCLE_PREFIX_NO_TOOLS, "dim"),
    (LIFECYCLE_PREFIX_TASK_COMPLETED, "green bold"),
    (LIFECYCLE_PREFIX_FALLBACK, "yellow dim"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_log_path() -> Path:
    """Return XDG-compliant log path."""
    xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(xdg_data) / "tunacode" / "logs" / "tunacode.log"


def _get_extra(record: logging.LogRecord) -> dict[str, object]:
    """Return the tunacode_extra dict attached to a stdlib LogRecord."""
    return getattr(record, TUNACODE_EXTRA_ATTR, {}) or {}


# ---------------------------------------------------------------------------
# Structured file formatter
# ---------------------------------------------------------------------------


class StructuredFormatter(logging.Formatter):
    """Format records as structured log lines for the file handler.

    Produces lines like:
        2024-01-15T10:30:45.123456+00:00 [INFO   ] req=abc123 iter=5 Operation completed
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(UTC).isoformat()
        level_name = record.levelname.ljust(7)
        parts: list[str] = [f"{ts} [{level_name}]"]

        extra = _get_extra(record)

        source = extra.get("source", "")
        if source:
            parts.append(f"[{source}]")

        request_id = extra.get("request_id", "")
        if request_id:
            parts.append(f"req={request_id}")

        iteration = extra.get("iteration", 0)
        if iteration:
            parts.append(f"iter={iteration}")

        tool_name = extra.get("tool_name", "")
        if tool_name:
            parts.append(f"tool={tool_name}")

        duration_ms = extra.get("duration_ms", 0.0)
        if duration_ms:
            parts.append(f"dur={duration_ms:.1f}ms")

        parts.append(record.getMessage())
        return " ".join(parts)


# ---------------------------------------------------------------------------
# FileHandler — stdlib RotatingFileHandler subclass
# ---------------------------------------------------------------------------


class FileHandler(logging.handlers.RotatingFileHandler):
    """Rotating file handler writing to ~/.local/share/tunacode/logs/tunacode.log.

    Delegates rotation to stdlib ``RotatingFileHandler``.
    """

    MAX_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    BACKUP_COUNT: int = 5

    def __init__(
        self,
        log_path: Path | None = None,
        min_level: int = logging.DEBUG,
    ) -> None:
        path = log_path or _default_log_path()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._log_path = path

        super().__init__(
            filename=str(path),
            maxBytes=self.MAX_SIZE_BYTES,
            backupCount=self.BACKUP_COUNT,
            encoding="utf-8",
        )
        self.setLevel(min_level)
        self.setFormatter(StructuredFormatter())

    @property
    def log_path(self) -> Path:
        return self._log_path


# ---------------------------------------------------------------------------
# TUIHandler — Rich-formatted handler for debug mode
# ---------------------------------------------------------------------------


class TUIHandler(logging.Handler):
    """Handler that pipes logs to RichLog when debug_mode is ON.

    Only active when explicitly enabled.  Uses a callback to write to the
    TUI without importing the UI layer.
    """

    def __init__(
        self,
        write_callback: TuiWriteCallback | None = None,
        min_level: int = logging.DEBUG,
    ) -> None:
        super().__init__(min_level)
        self._write_callback = write_callback
        self._enabled = False

    def set_write_callback(self, callback: TuiWriteCallback) -> None:
        """Set the callback for writing to TUI (injected from app)."""
        self._write_callback = callback

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def emit(self, record: logging.LogRecord) -> None:
        if not self._enabled:
            return
        if record.levelno < self.level:
            return
        if self._write_callback is None:
            return

        text = self._format_rich(record)
        self._write_callback(text)

    def _format_rich(self, record: logging.LogRecord) -> RenderableType:
        """Format record as Rich Text with styling based on content type."""
        from rich.text import Text

        msg = record.getMessage()

        # Detect lifecycle log type from message content and apply colors
        if msg.startswith("[LIFECYCLE]"):
            return self._format_lifecycle_record(msg[11:].strip())

        # Standard level-based styling
        style_map: dict[int, str] = {
            LogLevel.DEBUG: "dim",
            LogLevel.INFO: "",
            LogLevel.WARNING: "yellow",
            LogLevel.ERROR: "red bold",
            LogLevel.THOUGHT: "cyan italic",
            LogLevel.TOOL: "green",
        }

        style = style_map.get(record.levelno, "")
        prefix = f"[{record.levelname}]"

        text = Text()
        text.append(prefix, style="bold " + style)
        text.append(" ")
        text.append(msg, style=style)

        extra = _get_extra(record)
        tool_name = extra.get("tool_name", "")
        if tool_name:
            text.append(f" ({tool_name})", style="dim")
        duration_ms = extra.get("duration_ms", 0.0)
        if duration_ms:
            text.append(f" [{duration_ms:.0f}ms]", style="dim")

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

        # Iteration complete — dim
        if msg.startswith("Iteration") and "complete" in msg:
            text.append(msg, style="dim")
            return text

        # Default — dim for other lifecycle logs
        text.append(msg, style="dim")
        return text
