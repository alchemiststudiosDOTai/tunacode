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
