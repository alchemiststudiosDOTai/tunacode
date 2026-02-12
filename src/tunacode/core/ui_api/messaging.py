"""Core messaging facade for shared message helpers."""

from __future__ import annotations

from typing import Any

from tunacode.utils.messaging import estimate_messages_tokens as _estimate_messages_tokens
from tunacode.utils.messaging import estimate_tokens as _estimate_tokens
from tunacode.utils.messaging import get_content as _get_content

__all__: list[str] = ["estimate_messages_tokens", "estimate_tokens", "get_content"]


def get_content(message: Any) -> str:
    """Extract content from a message payload.

    Args:
        message: Message object or dict from the agent stack.

    Returns:
        The extracted message content string (may be empty).
    """
    return _get_content(message)


def estimate_tokens(text: str) -> int:
    """Estimate token count for plain text.

    UI is not allowed to import from ``tunacode.utils`` directly.
    """
    return _estimate_tokens(text)


def estimate_messages_tokens(messages: list[Any]) -> int:
    """Estimate total tokens for a list of messages.

    UI is not allowed to import from ``tunacode.utils`` directly.
    This facade keeps token estimation reachable from the UI layer while
    preserving the dependency direction.
    """
    return _estimate_messages_tokens(messages)
