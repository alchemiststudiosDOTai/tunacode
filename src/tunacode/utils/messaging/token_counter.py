"""Token counting utility using a lightweight heuristic.

Phase 6+ note:
TunaCode stores history as typed tinyagent messages in memory, and as tinyagent
JSON dicts at persistence boundaries.
This module intentionally supports:
- tinyagent message models
- tinyagent dict messages (serialization boundary)

Legacy pydantic-ai message objects are not supported.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias

from tinyagent.agent_types import AgentMessage, JsonObject

from tunacode.utils.messaging.adapter import get_content

CHARS_PER_TOKEN: int = 4
MessageInput: TypeAlias = AgentMessage | JsonObject


def estimate_tokens(text: str) -> int:
    """Estimate token count for plain text."""
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN


def estimate_message_tokens(message: MessageInput) -> int:
    """Estimate token count for a single message.

    This uses a rough chars-per-token heuristic. It is intended for UI
    budgeting and compaction heuristics, not billing-accurate accounting.
    """

    return estimate_tokens(get_content(message))


def estimate_messages_tokens(messages: Sequence[MessageInput]) -> int:
    """Estimate total token count for a list of messages."""

    total = 0
    for message in messages:
        total += estimate_message_tokens(message)
    return total
