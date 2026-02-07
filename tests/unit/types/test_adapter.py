"""Unit tests for the tinyagent message adapter.

These tests verify that tinyagent-style dict messages are correctly converted to
TunaCode's canonical message types, and that canonical messages can be converted
back to tinyagent dicts.

Legacy pydantic-ai message formats are intentionally not supported.
"""

from __future__ import annotations

import pytest

from tunacode.types.canonical import (
    CanonicalMessage,
    MessageRole,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThoughtPart,
    ToolCallPart,
    ToolReturnPart,
)
from tunacode.utils.messaging.adapter import (
    find_dangling_tool_calls,
    from_canonical,
    get_content,
    get_tool_call_ids,
    get_tool_return_ids,
    to_canonical,
)

# -----------------------------------------------------------------------------
# tinyagent message builders
# -----------------------------------------------------------------------------


def _text_item(text: str) -> dict[str, object]:
    return {"type": "text", "text": text, "text_signature": None}


def _thinking_item(thinking: str) -> dict[str, object]:
    return {"type": "thinking", "thinking": thinking, "thinking_signature": None}


def _tool_call_item(
    tool_call_id: str,
    tool_name: str,
    args: dict[str, object],
) -> dict[str, object]:
    return {
        "type": "tool_call",
        "id": tool_call_id,
        "name": tool_name,
        "arguments": args,
        "partial_json": "",
    }


def _user_message(text: str) -> dict[str, object]:
    return {"role": "user", "content": [_text_item(text)]}


def _assistant_message(*items: dict[str, object]) -> dict[str, object]:
    return {"role": "assistant", "content": list(items)}


def _system_message(text: str) -> dict[str, object]:
    return {"role": "system", "content": [_text_item(text)]}


def _tool_result_message(tool_call_id: str, tool_name: str, text: str) -> dict[str, object]:
    return {
        "role": "tool_result",
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "content": [_text_item(text)],
        "details": {},
        "is_error": False,
    }


class TestToCanonical:
    def test_user_message_to_canonical(self) -> None:
        msg = _user_message("Hello world")
        result = to_canonical(msg)

        assert result.role == MessageRole.USER
        assert result.parts == (TextPart(content="Hello world"),)

    def test_assistant_text_message_to_canonical(self) -> None:
        msg = _assistant_message(_text_item("I can help"))
        result = to_canonical(msg)

        assert result.role == MessageRole.ASSISTANT
        assert len(result.parts) == 1
        assert isinstance(result.parts[0], TextPart)
        assert result.parts[0].content == "I can help"

    def test_assistant_thinking_to_canonical(self) -> None:
        msg = _assistant_message(_thinking_item("thinking..."))
        result = to_canonical(msg)

        assert result.role == MessageRole.ASSISTANT
        assert result.parts == (ThoughtPart(content="thinking..."),)

    def test_assistant_tool_call_to_canonical(self) -> None:
        msg = _assistant_message(
            _tool_call_item("tc_123", "read_file", {"filepath": "/tmp/test.txt"})
        )
        result = to_canonical(msg)

        assert result.role == MessageRole.ASSISTANT
        assert len(result.parts) == 1
        assert isinstance(result.parts[0], ToolCallPart)
        part = result.parts[0]
        assert part.tool_call_id == "tc_123"
        assert part.tool_name == "read_file"
        assert part.args == {"filepath": "/tmp/test.txt"}

    def test_tool_result_to_canonical(self) -> None:
        msg = _tool_result_message("tc_123", "read_file", "file contents")
        result = to_canonical(msg)

        assert result.role == MessageRole.TOOL
        assert len(result.parts) == 1
        assert isinstance(result.parts[0], ToolReturnPart)
        assert result.parts[0].tool_call_id == "tc_123"
        assert result.parts[0].content == "file contents"

    def test_system_message_to_canonical(self) -> None:
        msg = _system_message("You are helpful")
        result = to_canonical(msg)

        assert result.role == MessageRole.SYSTEM
        assert result.parts == (SystemPromptPart(content="You are helpful"),)

    def test_missing_role_raises(self) -> None:
        with pytest.raises(TypeError, match="missing a non-empty 'role'"):
            to_canonical({"content": [_text_item("x")]})


class TestFromCanonical:
    def test_user_message_from_canonical(self) -> None:
        msg = CanonicalMessage(role=MessageRole.USER, parts=(TextPart(content="Hello"),))
        restored = from_canonical(msg)

        assert restored["role"] == "user"
        assert restored["content"][0]["type"] == "text"
        assert restored["content"][0]["text"] == "Hello"

    def test_assistant_tool_call_from_canonical(self) -> None:
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(ToolCallPart(tool_call_id="tc_1", tool_name="bash", args={"cmd": "ls"}),),
        )
        restored = from_canonical(msg)

        assert restored["role"] == "assistant"
        assert restored["content"][0]["type"] == "tool_call"
        assert restored["content"][0]["id"] == "tc_1"
        assert restored["content"][0]["name"] == "bash"
        assert restored["content"][0]["arguments"] == {"cmd": "ls"}

    def test_tool_result_from_canonical(self) -> None:
        msg = CanonicalMessage(
            role=MessageRole.TOOL,
            parts=(ToolReturnPart(tool_call_id="tc_1", content="ok"),),
        )
        restored = from_canonical(msg)

        assert restored["role"] == "tool_result"
        assert restored["tool_call_id"] == "tc_1"
        assert restored["content"][0]["type"] == "text"
        assert restored["content"][0]["text"] == "ok"

    def test_retry_prompt_part_is_text(self) -> None:
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(RetryPromptPart(tool_call_id="tc", tool_name="bash", content="try again"),),
        )
        restored = from_canonical(msg)

        assert restored["role"] == "user"
        assert restored["content"][0]["type"] == "text"
        assert restored["content"][0]["text"] == "try again"


class TestRoundTrip:
    def test_user_round_trip_content(self) -> None:
        original = _user_message("hello")
        canonical = to_canonical(original)
        restored = from_canonical(canonical)

        assert restored["role"] == "user"
        assert get_content(restored) == "hello"

    def test_assistant_tool_call_round_trip(self) -> None:
        original = _assistant_message(_tool_call_item("tc_abc", "read_file", {"filepath": "/x"}))
        canonical = to_canonical(original)
        restored = from_canonical(canonical)

        assert restored["role"] == "assistant"
        assert get_tool_call_ids(restored) == {"tc_abc"}


class TestExtractionHelpers:
    def test_get_content_from_canonical(self) -> None:
        msg = CanonicalMessage(role=MessageRole.USER, parts=(TextPart(content="Direct"),))
        assert get_content(msg) == "Direct"

    def test_get_tool_call_ids_from_assistant_message(self) -> None:
        msg = _assistant_message(
            _tool_call_item("tc_1", "a", {}),
            _tool_call_item("tc_2", "b", {}),
        )
        assert get_tool_call_ids(msg) == {"tc_1", "tc_2"}

    def test_get_tool_return_ids_from_tool_result_message(self) -> None:
        msg = _tool_result_message("tc_1", "a", "done")
        assert get_tool_return_ids(msg) == {"tc_1"}

    def test_find_dangling_tool_calls(self) -> None:
        messages = [
            _assistant_message(
                _tool_call_item("tc_1", "a", {}),
                _tool_call_item("tc_2", "b", {}),
            ),
            _tool_result_message("tc_1", "a", "done"),
        ]

        assert find_dangling_tool_calls(messages) == {"tc_2"}

    def test_find_dangling_no_dangling(self) -> None:
        messages = [
            _assistant_message(_tool_call_item("tc_1", "a", {})),
            _tool_result_message("tc_1", "a", "done"),
        ]

        assert find_dangling_tool_calls(messages) == set()
