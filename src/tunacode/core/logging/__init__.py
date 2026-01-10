"""TunaCode unified logging system.

Usage:
    from tunacode.core.logging import get_logger, LogLevel

    logger = get_logger()
    logger.info("Starting request", request_id="abc123")
    logger.tool("bash", "Executing command", duration_ms=150.5)
"""

from tunacode.core.logging.handlers import FileHandler, Handler, TUIHandler
from tunacode.core.logging.levels import LogLevel
from tunacode.core.logging.manager import LogManager, get_logger
from tunacode.core.logging.records import LogRecord

__all__ = [
    "FileHandler",
    "Handler",
    "LogLevel",
    "LogManager",
    "LogRecord",
    "TUIHandler",
    "get_logger",
]
