"""Logging helpers for tool_dispatcher."""

from typing import Any

from tunacode.types import ToolArgs

from tunacode.core.logging import get_logger

from ._tool_dispatcher_constants import TOOL_NAMES_DISPLAY_LIMIT, UNKNOWN_TOOL_NAME


def _log_dispatch_summary(
    records: list[tuple[Any, ToolArgs]],
    elapsed_ms: float,
) -> None:
    """Log a summary of dispatched tool calls."""
    logger = get_logger()
    total = len(records)

    if not total:
        logger.lifecycle("No tool calls this iteration")
        return

    names = [getattr(part, "tool_name", UNKNOWN_TOOL_NAME) for part, _ in records]
    names_str = ", ".join(names[:TOOL_NAMES_DISPLAY_LIMIT])
    if len(names) > TOOL_NAMES_DISPLAY_LIMIT:
        names_str += f" (+{len(names) - TOOL_NAMES_DISPLAY_LIMIT} more)"

    logger.lifecycle(f"Tools: [{names_str}] ({total} total, {elapsed_ms:.0f}ms)")
