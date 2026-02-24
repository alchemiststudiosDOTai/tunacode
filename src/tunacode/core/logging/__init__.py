"""TunaCode unified logging system.

Built on Python's stdlib ``logging`` with automatic redaction of sensitive
data (API keys, passwords, emails, bearer tokens).

Usage::

    from tunacode.core.logging import get_logger, LogLevel

    logger = get_logger()
    logger.info("Starting request", request_id="abc123")
    logger.tool("bash", "Executing command", duration_ms=150.5)
"""

from tunacode.core.logging.handlers import FileHandler, TUIHandler
from tunacode.core.logging.levels import LogLevel
from tunacode.core.logging.manager import LogManager, get_logger
from tunacode.core.logging.redaction import RedactingFilter

__all__ = [
    "FileHandler",
    "LogLevel",
    "LogManager",
    "RedactingFilter",
    "TUIHandler",
    "get_logger",
]
