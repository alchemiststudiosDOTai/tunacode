"""Log level definitions for TunaCode logging system."""

from enum import IntEnum


class LogLevel(IntEnum):
    """Log levels with semantic extensions for agent operations.

    Standard levels (10-40) plus semantic levels (50+) for agent-specific events.
    """

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    THOUGHT = 50  # Agent reasoning/thinking
    TOOL = 60  # Tool invocations and results
