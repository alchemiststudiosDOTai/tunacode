"""Indexing orchestration service - manages CodeIndex lifecycle.

This service encapsulates the two-phase indexing strategy and threading,
providing a clean interface for the UI layer via status callbacks.
The UI layer should never import from tunacode.indexing directly.

Dependency flow: ui -> core (this service) -> indexing
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from tunacode.indexing import CodeIndex
from tunacode.indexing.constants import QUICK_INDEX_THRESHOLD

# Status callback type: (message, style) -> None
# Style values: "muted", "success"
StatusCallback = Callable[[str, str], None]


class IndexingService:
    """Manages code indexing lifecycle for the application.

    Encapsulates the two-phase indexing strategy:
    - Small codebases (<1000 files): Full index immediately
    - Large codebases (>=1000 files): Priority index first, then expand

    All status updates are communicated via callback, never direct UI access.
    """

    def __init__(self, status_callback: StatusCallback | None = None) -> None:
        """Initialize the indexing service.

        Args:
            status_callback: Optional callback for status updates.
                            Receives (message, style) where style is "muted" or "success".
        """
        self._status_callback = status_callback

    def set_status_callback(self, callback: StatusCallback | None) -> None:
        """Set or update the status callback.

        Args:
            callback: Callback for status updates, or None to disable.
        """
        self._status_callback = callback

    def _notify(self, message: str, style: str) -> None:
        """Send status notification if callback is set.

        Args:
            message: Status message text.
            style: Style hint ("muted" or "success").
        """
        if self._status_callback is not None:
            self._status_callback(message, style)

    async def start_startup_index(self) -> tuple[int, int | None, bool]:
        """Build startup index with dynamic sizing.

        For small codebases (< QUICK_INDEX_THRESHOLD files), builds full index.
        For large codebases, builds priority index first.

        Returns:
            Tuple of (indexed_count, total_or_none, is_partial).
            - indexed_count: Number of files indexed
            - total_or_none: Total file count if partial, None if full
            - is_partial: True if priority index only (needs expand)
        """

        def do_index() -> tuple[int, int | None, bool]:
            index = CodeIndex.get_instance()
            total = index.quick_count()

            if total < QUICK_INDEX_THRESHOLD:
                index.build_index()
                return len(index._all_files), None, False
            else:
                count = index.build_priority_index()
                return count, total, True

        indexed, total, is_partial = await asyncio.to_thread(do_index)

        if is_partial:
            self._notify(
                f"Code cache: {indexed}/{total} files indexed, expanding...",
                "muted",
            )
        else:
            self._notify(
                f"Code cache built: {indexed} files indexed",
                "success",
            )

        return indexed, total, is_partial

    async def expand_index(self) -> int:
        """Expand partial index to full index in background.

        Safe to call even if index is already full (will no-op).

        Returns:
            Final count of indexed files.
        """

        def do_expand() -> int:
            index = CodeIndex.get_instance()
            index.expand_index()
            return len(index._all_files)

        final_count = await asyncio.to_thread(do_expand)

        self._notify(
            f"Code cache built: {final_count} files indexed",
            "success",
        )

        return final_count

    async def run_full_startup(self) -> int:
        """Run complete startup indexing workflow.

        Convenience method that runs start_startup_index and, if partial,
        automatically expands. Returns final indexed file count.

        Returns:
            Total number of files indexed after completion.
        """
        indexed, total, is_partial = await self.start_startup_index()

        if is_partial:
            return await self.expand_index()

        return indexed
