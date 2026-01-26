"""Startup tasks for the TUI - index building and initialization."""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual.widgets import RichLog

from tunacode.indexing import CodeIndex
from tunacode.indexing.constants import QUICK_INDEX_THRESHOLD

from tunacode.ui.styles import STYLE_MUTED, STYLE_SUCCESS


async def run_startup_index(rich_log: RichLog) -> None:
    """Build startup index with dynamic sizing.

    For small codebases (< QUICK_INDEX_THRESHOLD files), builds full index.
    For large codebases, builds priority index first, then expands in background.
    """

    def do_index() -> tuple[int, int | None, bool]:
        """Returns (indexed_count, total_or_none, is_partial)."""
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
        msg = Text()
        msg.append(
            f"Code cache: {indexed}/{total} files indexed, expanding...",
            style=STYLE_MUTED,
        )
        rich_log.write(msg)

        # Expand in background
        def do_expand() -> int:
            index = CodeIndex.get_instance()
            index.expand_index()
            return len(index._all_files)

        final_count = await asyncio.to_thread(do_expand)
        done_msg = Text()
        done_msg.append(f"⚙ Code cache built: {final_count} files indexed", style=STYLE_SUCCESS)
        rich_log.write(done_msg)
    else:
        msg = Text()
        msg.append(f"⚙ Code cache built: {indexed} files indexed", style=STYLE_SUCCESS)
        rich_log.write(msg)
