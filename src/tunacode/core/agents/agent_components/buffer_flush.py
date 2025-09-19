"""Utilities for flushing buffered read-only tool calls."""

from __future__ import annotations

import time
from typing import Optional

from tunacode.core.logging.logger import get_logger
from tunacode.types import StateManager, ToolCallback
from tunacode.ui import console as ui
from tunacode.ui.tool_descriptions import get_batch_description

from .tool_buffer import ToolBuffer
from .tool_executor import execute_tools_parallel

logger = get_logger(__name__)


async def flush_buffered_read_only_tools(
    tool_buffer: Optional[ToolBuffer],
    tool_callback: Optional[ToolCallback],
    state_manager: StateManager,
    *,
    origin: str = "buffered-tools",
    detailed: bool = False,
    banner: Optional[str] = None,
) -> bool:
    """Execute buffered read-only tools and report whether any work was performed."""
    if tool_buffer is None or tool_callback is None or not tool_buffer.has_tasks():
        return False

    buffered_tasks = tool_buffer.flush()
    if not buffered_tasks:
        return False

    batch_id = getattr(state_manager.session, "batch_counter", 0) + 1
    setattr(state_manager.session, "batch_counter", batch_id)

    tool_names = [getattr(part, "tool_name", "tool") for part, _ in buffered_tasks]

    try:
        batch_msg = get_batch_description(len(buffered_tasks), tool_names)
        await ui.update_spinner_message(
            f"[bold #00d7ff]{batch_msg}...[/bold #00d7ff]", state_manager
        )

        if detailed:
            header = banner or origin.upper()
            await ui.muted("\n" + "=" * 60)
            await ui.muted(
                f"🚀 {header}: Executing {len(buffered_tasks)} read-only tools concurrently"
            )
            await ui.muted("=" * 60)
            for idx, (part, _node) in enumerate(buffered_tasks, start=1):
                tool_desc = f"  [{idx}] {getattr(part, 'tool_name', 'tool')}"
                args = getattr(part, "args", {})
                if isinstance(args, dict):
                    if part.tool_name == "read_file" and "file_path" in args:
                        tool_desc += f" → {args['file_path']}"
                    elif part.tool_name == "grep" and "pattern" in args:
                        tool_desc += f" → pattern: '{args['pattern']}'"
                        if "include_files" in args:
                            tool_desc += f", files: '{args['include_files']}'"
                    elif part.tool_name == "list_dir" and "directory" in args:
                        tool_desc += f" → {args['directory']}"
                    elif part.tool_name == "glob" and "pattern" in args:
                        tool_desc += f" → pattern: '{args['pattern']}'"
                await ui.muted(tool_desc)
            await ui.muted("=" * 60)
        elif state_manager.session.show_thoughts:
            await ui.muted(f"⚡ {origin}: executing {len(buffered_tasks)} buffered read-only tools")
    except Exception:  # pragma: no cover - UI best effort
        logger.debug("Buffered tool flush UI failed (non-fatal)", exc_info=True)

    start = time.time()
    await execute_tools_parallel(buffered_tasks, tool_callback)
    elapsed_ms = (time.time() - start) * 1000.0

    if detailed:
        try:
            sequential_estimate = len(buffered_tasks) * 100.0
            speedup = (sequential_estimate / elapsed_ms) if elapsed_ms > 0 else 1.0
            await ui.muted(
                f"Batch completed in {elapsed_ms:.1f} ms (estimated speedup ×{speedup:.2f})"
            )
            await ui.muted("=" * 60)
        except Exception:  # pragma: no cover - UI best effort
            logger.debug(
                "Buffered tool flush metrics display failed (non-fatal)",
                exc_info=True,
            )

    return True
