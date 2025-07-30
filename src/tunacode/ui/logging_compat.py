"""
UILogger compatibility layer for unified logging.

Implements the UILogger protocol using the unified logging system,
preserving UI formatting and behavior for all log levels.
"""

from tunacode.core.logging.logger import get_logger
from tunacode.types import UILogger


class UnifiedUILogger(UILogger):
    """
    UILogger implementation that routes all UI log calls through the unified logging system.
    Preserves UI conventions for info, error, warning, debug, and success.
    """

    def __init__(self, name: str = "ui"):
        self.logger = get_logger(name)

    async def info(self, message: str) -> None:
        # Standard info log
        self.logger.info(message)

    async def error(self, message: str) -> None:
        # Standard error log
        self.logger.error(message)

    async def warning(self, message: str) -> None:
        # Standard warning log
        self.logger.warning(message)

    async def debug(self, message: str) -> None:
        # Standard debug log
        self.logger.debug(message)

    async def success(self, message: str) -> None:
        # "Success" is a UI convention; log as info with a marker for UI formatting
        # Add a special prefix or extra field for downstream handlers/formatters
        self.logger.info(f"[SUCCESS] {message}", extra={"ui_success": True})


# Singleton instance for convenience
ui_logger: UILogger = UnifiedUILogger()
