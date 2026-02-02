"""Token counting utility using a lightweight heuristic."""

from __future__ import annotations

from typing import Any

CHARS_PER_TOKEN: int = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count for plain text."""
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN


def estimate_message_tokens(message: Any) -> int:
    """Estimate token count for a single message."""
    total_length = 0

    # Note: This defensive handling of mixed message types is temporary.
    # Once pydantic-ai is fully removed and messages use a single format,
    # this can be simplified to work with the canonical type directly.
    parts = getattr(message, "parts", None)
    if parts:
        for part in parts:
            if isinstance(part, dict):
                content = part.get("content")
            else:
                content = getattr(part, "content", None)
            if content:
                total_length += len(str(content))
        return total_length // CHARS_PER_TOKEN

    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)

    if content:
        return len(str(content)) // CHARS_PER_TOKEN

    return 0


def estimate_messages_tokens(messages: list[Any]) -> int:
    """Estimate total token count for a list of messages."""
    total = 0
    for message in messages:
        total += estimate_message_tokens(message)
    return total
