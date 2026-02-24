"""Log level definitions for TunaCode logging system.

Registers custom agent-specific levels with Python's stdlib logging.
Standard levels (10-40) match stdlib logging exactly.
"""

import logging
from enum import IntEnum

# Custom agent-specific levels.
# Placed between ERROR(40) and CRITICAL(50) to avoid overriding stdlib CRITICAL.
THOUGHT_LEVEL: int = 45
TOOL_LEVEL: int = 46

logging.addLevelName(THOUGHT_LEVEL, "THOUGHT")
logging.addLevelName(TOOL_LEVEL, "TOOL")


class LogLevel(IntEnum):
    """Log levels with semantic extensions for agent operations.

    Standard levels (10-40) match stdlib logging.
    Semantic levels (45-46) for agent-specific events.
    """

    DEBUG = logging.DEBUG  # 10
    INFO = logging.INFO  # 20
    WARNING = logging.WARNING  # 30
    ERROR = logging.ERROR  # 40
    THOUGHT = THOUGHT_LEVEL  # 45 — Agent reasoning/thinking
    TOOL = TOOL_LEVEL  # 46 — Tool invocations and results
