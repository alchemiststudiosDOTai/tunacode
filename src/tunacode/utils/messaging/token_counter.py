"""Token counting utility using a lightweight heuristic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tunacode.types.canonical import CanonicalMessage
from tunacode.utils.messaging.adapter import to_canonical

CHARS_PER_TOKEN: int = 4
EMPTY_TEXT: str = ""
EMPTY_TEXT_LENGTH: int = 0
EMPTY_TOKEN_COUNT: int = 0
SPACE_SEPARATOR: str = " "
SPACE_SEPARATOR_LENGTH: int = len(SPACE_SEPARATOR)
SPACE_SEPARATOR_COUNT_OFFSET: int = 1


@dataclass(slots=True)
class MessageTokenCacheEntry:
    """Cached token metadata for a single message."""

    text_length: int
    token_count: int


class MessageTokenCache:
    """Cache token counts per message using text length signatures."""

    def __init__(self) -> None:
        self._entries: dict[int, MessageTokenCacheEntry] = {}

    def rebuild_total(self, messages: list[Any]) -> int:
        """Recompute total tokens, reusing cached entries when possible."""
        total_tokens = EMPTY_TOKEN_COUNT
        active_message_ids: set[int] = set()

        for message in messages:
            message_id = id(message)
            active_message_ids.add(message_id)
            token_count = self._get_or_update(message_id, message)
            total_tokens += token_count

        self._prune(active_message_ids)
        return total_tokens

    def clear(self) -> None:
        """Remove all cached entries."""
        self._entries.clear()

    def _get_or_update(self, message_id: int, message: Any) -> int:
        text_length = get_message_text_length(message)
        cached_entry = self._entries.get(message_id)

        if cached_entry is not None and cached_entry.text_length == text_length:
            return cached_entry.token_count

        token_count = estimate_tokens_from_length(text_length)
        self._entries[message_id] = MessageTokenCacheEntry(
            text_length=text_length,
            token_count=token_count,
        )
        return token_count

    def _prune(self, active_message_ids: set[int]) -> None:
        stale_ids = [
            message_id for message_id in self._entries if message_id not in active_message_ids
        ]
        for message_id in stale_ids:
            del self._entries[message_id]


def estimate_tokens(text: str, model_name: str | None = None) -> int:
    """
    Estimate token count using a simple character heuristic.

    Args:
        text: The text to count tokens for.
        model_name: Optional model name (unused).

    Returns:
        The estimated number of tokens.
    """
    if not text:
        return EMPTY_TOKEN_COUNT

    text_length = len(text)
    return estimate_tokens_from_length(text_length)


def estimate_tokens_from_length(text_length: int) -> int:
    """Estimate token count from a precomputed character length."""
    if text_length <= EMPTY_TEXT_LENGTH:
        return EMPTY_TOKEN_COUNT

    return text_length // CHARS_PER_TOKEN


def get_message_text_length(message: Any) -> int:
    """Return the effective text length used by canonical content extraction."""
    canonical_message = _canonicalize_message(message)
    return _canonical_text_length(canonical_message)


def _canonicalize_message(message: Any) -> CanonicalMessage:
    if isinstance(message, CanonicalMessage):
        return message
    return to_canonical(message)


def _canonical_text_length(message: CanonicalMessage) -> int:
    parts = message.parts
    if not parts:
        return EMPTY_TEXT_LENGTH

    content_length = EMPTY_TEXT_LENGTH
    for part in parts:
        content_value = getattr(part, "content", EMPTY_TEXT)
        content_text = _normalize_segment(content_value)
        content_length += len(content_text)

    space_count = len(parts) - SPACE_SEPARATOR_COUNT_OFFSET
    return content_length + (space_count * SPACE_SEPARATOR_LENGTH)


def _normalize_segment(value: Any) -> str:
    if value is None:
        return EMPTY_TEXT
    return str(value)
