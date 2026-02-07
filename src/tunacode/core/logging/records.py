"""Log record container for TunaCode logging system."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from tunacode.core.logging.levels import LogLevel


@dataclass(frozen=True)
class LogRecord:
    """Immutable log record containing all event metadata."""

    level: LogLevel
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""  # Module/component name
    request_id: str = ""  # Ties to session.runtime.request_id
    iteration: int = 0  # Agent iteration number
    tool_name: str = ""  # For TOOL level logs
    duration_ms: float = 0.0  # For timing information
    extra: dict[str, Any] = field(default_factory=dict)  # Additional context

    def to_dict(self) -> dict[str, Any]:
        """Return all fields as a JSON-serializable dict."""
        result: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.name.lower(),
            "event": self.message,
        }
        if self.source:
            result["source"] = self.source
        if self.request_id:
            result["request_id"] = self.request_id
        result["iteration"] = self.iteration
        if self.tool_name:
            result["tool_name"] = self.tool_name
        result["duration_ms"] = self.duration_ms
        if self.extra:
            if "extra" in self.extra:
                raise ValueError(
                    "LogRecord.extra must not contain an 'extra' key to avoid ambiguous nesting"
                )
            result["extra"] = self.extra
        return result
