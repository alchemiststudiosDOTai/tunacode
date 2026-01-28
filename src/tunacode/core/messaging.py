"""Core messaging facade for shared message helpers."""

from __future__ import annotations

from typing import Any

from tunacode.utils.messaging import get_content as _get_content

__all__: list[str] = ["get_content"]


def get_content(message: Any) -> str:
    """Extract content from a message payload.

    Args:
        message: Message object or dict from the agent stack.

    Returns:
        The extracted message content string (may be empty).
    """
    return _get_content(message)
