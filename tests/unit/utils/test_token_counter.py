"""Tests for token counting heuristics."""

from __future__ import annotations

from tunacode.types.canonical import CanonicalMessage, MessageRole, TextPart
from tunacode.utils.messaging.token_counter import (
    CHARS_PER_TOKEN,
    estimate_message_tokens,
    estimate_messages_tokens,
    estimate_tokens,
)


class FakeMessage:
    """Message with parts attribute."""

    def __init__(self, parts: list) -> None:
        self.parts = parts


class FakePart:
    """Part with content attribute."""

    def __init__(self, content: str) -> None:
        self.content = content


def test_estimate_tokens_empty() -> None:
    assert estimate_tokens("") == 0


def test_estimate_tokens_basic() -> None:
    text = "a" * CHARS_PER_TOKEN
    assert estimate_tokens(text) == 1


def test_estimate_tokens_multiple() -> None:
    text = "a" * (CHARS_PER_TOKEN * 5)
    assert estimate_tokens(text) == 5


def test_estimate_message_tokens_with_parts() -> None:
    parts = [FakePart("aaaa"), FakePart("bbbb")]
    message = FakeMessage(parts)
    assert estimate_message_tokens(message) == 2


def test_estimate_message_tokens_with_content() -> None:
    message = {"content": "a" * 8}
    assert estimate_message_tokens(message) == 2


def test_estimate_message_tokens_empty_parts() -> None:
    message = FakeMessage([])
    assert estimate_message_tokens(message) == 0


def test_estimate_message_tokens_no_content() -> None:
    message = {}
    assert estimate_message_tokens(message) == 0


def test_estimate_messages_tokens_multiple() -> None:
    messages = [
        FakeMessage([FakePart("aaaa")]),
        FakeMessage([FakePart("bbbb")]),
    ]
    assert estimate_messages_tokens(messages) == 2


def test_estimate_messages_tokens_empty_list() -> None:
    assert estimate_messages_tokens([]) == 0


def test_estimate_message_tokens_canonical() -> None:
    parts = (TextPart(content="aaaa"), TextPart(content="bbbb"))
    message = CanonicalMessage(role=MessageRole.USER, parts=parts)
    assert estimate_message_tokens(message) == 2


def test_estimate_message_tokens_dict_parts() -> None:
    """Parts can be dicts (serialized pydantic-ai format)."""
    parts = [{"content": "aaaa"}, {"content": "bbbb"}]
    message = FakeMessage(parts)
    assert estimate_message_tokens(message) == 2


def test_estimate_message_tokens_mixed_parts() -> None:
    """Parts can mix objects and dicts."""
    parts = [FakePart("aaaa"), {"content": "bbbb"}]
    message = FakeMessage(parts)
    assert estimate_message_tokens(message) == 2
