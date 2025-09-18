"""Coordinator that serializes tool buffer flushing and validation."""

from __future__ import annotations

import asyncio
from typing import Optional

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.types import ToolCallback

from .buffer_flush import flush_buffered_read_only_tools
from .tool_buffer import ToolBuffer
from .tool_validation import ToolExecutionValidator

logger = get_logger(__name__)


class ToolFlushCoordinator:
    """Central coordinator to flush buffered tools before provider requests."""

    def __init__(
        self,
        state_manager: StateManager,
        tool_buffer: Optional[ToolBuffer],
        tool_callback: Optional[ToolCallback],
    ) -> None:
        self._state_manager = state_manager
        self._tool_buffer = tool_buffer
        self._tool_callback = tool_callback
        self._validator = ToolExecutionValidator(state_manager)
        self._lock = asyncio.Lock()

    @property
    def validator(self) -> ToolExecutionValidator:
        """Expose validator for callers needing direct access."""
        return self._validator

    async def ensure_before_request(self, origin: str) -> None:
        """Flush buffered tools and reconcile orphaned calls before API requests."""
        await self.flush(origin=origin)

    async def flush(
        self,
        *,
        origin: str,
        detailed: bool = False,
        banner: Optional[str] = None,
    ) -> bool:
        """Flush buffered read-only tools and reconcile orphaned calls."""
        async with self._lock:
            executed = await flush_buffered_read_only_tools(
                self._tool_buffer,
                self._tool_callback,
                self._state_manager,
                origin=origin,
                detailed=detailed,
                banner=banner,
            )

            patched, orphans = self._validator.reconcile_orphans(origin=origin)
            if patched:
                logger.info(
                    "Patched %d orphaned tool call(s) after flush (origin=%s)",
                    len(orphans),
                    origin,
                )
            return executed or patched
