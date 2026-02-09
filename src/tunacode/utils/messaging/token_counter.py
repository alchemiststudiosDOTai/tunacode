"""Token counting utility using a lightweight heuristic.

Phase 6+ note:
TunaCode stores history as tinyagent-style dict messages.
This module intentionally supports only:
- tinyagent dict messages
- :class:`~tunacode.types.canonical.CanonicalMessage`

Legacy pydantic-ai message objects are not supported.
"""

from __future__ import annotations

from typing import Any

from tunacode.types.canonical import CanonicalMessage, ToolCallPart
from tunacode.utils.messaging.adapter import to_canonical

CHARS_PER_TOKEN: int = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count for plain text."""
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN


def estimate_message_tokens(message: Any) -> int:
    """Estimate token count for a single message.

    This uses a rough chars-per-token heuristic. It is intended for UI
    budgeting and compaction heuristics, not billing-accurate accounting.
    """

    canonical = message if isinstance(message, CanonicalMessage) else to_canonical(message)

    total_chars = 0
    for part in canonical.parts:
        if isinstance(part, ToolCallPart):
            total_chars += len(part.tool_call_id) + len(part.tool_name) + len(str(part.args))
            continue

        content_value = getattr(part, "content", None)
        if content_value is None:
            continue

        content_text = content_value if isinstance(content_value, str) else str(content_value)
        total_chars += len(content_text)

    return total_chars // CHARS_PER_TOKEN


def estimate_messages_tokens(messages: list[Any]) -> int:
    """Estimate total token count for a list of messages."""

    total = 0
    for message in messages:
        total += estimate_message_tokens(message)
    return total
