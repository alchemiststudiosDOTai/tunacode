"""History filtering at summary checkpoints.

Implements filterCompacted equivalent from OpenCode - truncates history
at the most recent summary checkpoint to reduce context while preserving
essential information.
"""

from __future__ import annotations

from typing import Any

from tunacode.core.agents.resume.prune import prune_old_tool_outputs
from tunacode.core.agents.resume.summary import is_summary_message
from tunacode.core.logging import get_logger

__all__ = [
    "filter_compacted",
    "prepare_history",
]


def filter_compacted(messages: list[Any]) -> list[Any]:
    """Truncate history at the most recent summary checkpoint.

    Scans backwards through message history to find the most recent
    summary checkpoint message. Returns only messages from that point
    forward, effectively discarding older history that has been
    summarized.

    Args:
        messages: Full message history

    Returns:
        Truncated message list starting from last summary (or full list if none)
    """
    if not messages:
        return messages

    logger = get_logger()

    # Scan backwards for most recent summary
    for i in range(len(messages) - 1, -1, -1):
        if is_summary_message(messages[i]):
            truncated_count = i
            logger.lifecycle(f"Truncating {truncated_count} messages at summary checkpoint")
            return messages[i:]

    # No summary found, return full history
    return messages


def prepare_history(
    messages: list[Any],
    model_name: str,
) -> tuple[list[Any], int]:
    """Prepare message history for resume by filtering and pruning.

    Combines filter_compacted and prune_old_tool_outputs into a single
    operation that:
    1. Truncates at summary checkpoint (if present)
    2. Prunes old tool outputs beyond protection threshold

    Args:
        messages: Full message history
        model_name: Model for token estimation

    Returns:
        Tuple of (prepared messages, tokens reclaimed)
    """
    # First, filter at summary checkpoint
    filtered = filter_compacted(messages)

    # Then prune old tool outputs
    pruned, tokens_reclaimed = prune_old_tool_outputs(filtered, model_name)

    return (pruned, tokens_reclaimed)
