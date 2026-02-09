"""Tests for token counting heuristics."""

from __future__ import annotations

from tunacode.types.canonical import CanonicalMessage, MessageRole, TextPart, ToolCallPart
from tunacode.utils.messaging.token_counter import (
    CHARS_PER_TOKEN,
    estimate_message_tokens,
    estimate_messages_tokens,
    estimate_tokens,
)


def test_estimate_tokens_empty() -> None:
    assert estimate_tokens("") == 0


def test_estimate_tokens_basic() -> None:
    text = "a" * CHARS_PER_TOKEN
    assert estimate_tokens(text) == 1


def test_estimate_tokens_multiple() -> None:
    text = "a" * (CHARS_PER_TOKEN * 5)
    assert estimate_tokens(text) == 5


def test_estimate_message_tokens_tinyagent_text() -> None:
    message = {
        "role": "user",
        "content": [{"type": "text", "text": "a" * 8, "text_signature": None}],
    }
    assert estimate_message_tokens(message) == 2


def test_estimate_message_tokens_empty_content_list() -> None:
    message = {"role": "assistant", "content": []}
    assert estimate_message_tokens(message) == 0


def test_estimate_message_tokens_no_content() -> None:
    message = {"role": "assistant"}
    assert estimate_message_tokens(message) == 0


def test_estimate_messages_tokens_multiple() -> None:
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "aaaa", "text_signature": None}],
        },
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "bbbb", "text_signature": None}],
        },
    ]
    assert estimate_messages_tokens(messages) == 2


def test_estimate_messages_tokens_empty_list() -> None:
    assert estimate_messages_tokens([]) == 0


def test_estimate_message_tokens_canonical() -> None:
    parts = (TextPart(content="aaaa"), TextPart(content="bbbb"))
    message = CanonicalMessage(role=MessageRole.USER, parts=parts)
    assert estimate_message_tokens(message) == 2


def test_estimate_message_tokens_tool_call_counts_args() -> None:
    message = CanonicalMessage(
        role=MessageRole.ASSISTANT,
        parts=(ToolCallPart(tool_call_id="tc_1", tool_name="bash", args={"cmd": "ls"}),),
    )

    expected_chars = len("tc_1") + len("bash") + len(str({"cmd": "ls"}))
    assert estimate_message_tokens(message) == expected_chars // CHARS_PER_TOKEN
