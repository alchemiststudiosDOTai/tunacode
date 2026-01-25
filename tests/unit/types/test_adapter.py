"""Unit tests for the message adapter.

These tests verify that:
1. All legacy message formats are correctly converted to canonical
2. Round-trip conversion preserves content
3. get_content() produces the same output as legacy get_message_content()
"""

import pytest

from tunacode.types.canonical import (
    CanonicalMessage,
    MessageRole,
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
from tunacode.utils.messaging.message_utils import get_message_content


class TestToCanonical:
    """Tests for to_canonical() conversion."""

    def test_dict_with_content_key(self) -> None:
        """Legacy format: dict with 'content' key."""
        msg = {"content": "Hello world"}
        result = to_canonical(msg)

        assert result.role == MessageRole.USER
        assert len(result.parts) == 1
        assert isinstance(result.parts[0], TextPart)
        assert result.parts[0].content == "Hello world"

    def test_dict_with_thought_key(self) -> None:
        """Legacy format: dict with 'thought' key."""
        msg = {"thought": "I should think about this"}
        result = to_canonical(msg)

        assert result.role == MessageRole.ASSISTANT
        assert len(result.parts) == 1
        assert isinstance(result.parts[0], ThoughtPart)
        assert result.parts[0].content == "I should think about this"

    def test_dict_with_parts_text(self) -> None:
        """Dict with parts list containing text."""
        msg = {
            "kind": "request",
            "parts": [
                {"part_kind": "user-prompt", "content": "What is 2+2?"},
            ],
        }
        result = to_canonical(msg)

        assert result.role == MessageRole.USER
        assert len(result.parts) == 1
        assert isinstance(result.parts[0], TextPart)
        assert result.parts[0].content == "What is 2+2?"

    def test_dict_with_parts_tool_call(self) -> None:
        """Dict with parts list containing tool call."""
        msg = {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "tool-call",
                    "tool_call_id": "tc_123",
                    "tool_name": "read_file",
                    "args": {"filepath": "/tmp/test.txt"},
                },
            ],
        }
        result = to_canonical(msg)

        assert result.role == MessageRole.ASSISTANT
        assert len(result.parts) == 1
        assert isinstance(result.parts[0], ToolCallPart)
        assert result.parts[0].tool_call_id == "tc_123"
        assert result.parts[0].tool_name == "read_file"
        assert result.parts[0].args == {"filepath": "/tmp/test.txt"}

    def test_dict_with_parts_tool_return(self) -> None:
        """Dict with parts list containing tool return."""
        msg = {
            "kind": "request",
            "parts": [
                {
                    "part_kind": "tool-return",
                    "tool_call_id": "tc_123",
                    "content": "file contents here",
                },
            ],
        }
        result = to_canonical(msg)

        assert result.role == MessageRole.USER
        assert len(result.parts) == 1
        assert isinstance(result.parts[0], ToolReturnPart)
        assert result.parts[0].tool_call_id == "tc_123"
        assert result.parts[0].content == "file contents here"

    def test_dict_with_parts_system_prompt(self) -> None:
        """Dict with parts containing system prompt."""
        msg = {
            "kind": "request",
            "parts": [
                {"part_kind": "system-prompt", "content": "You are helpful."},
            ],
        }
        result = to_canonical(msg)

        assert result.role == MessageRole.USER
        assert len(result.parts) == 1
        assert isinstance(result.parts[0], SystemPromptPart)
        assert result.parts[0].content == "You are helpful."

    def test_dict_with_mixed_parts(self) -> None:
        """Dict with multiple part types."""
        msg = {
            "kind": "response",
            "parts": [
                {"part_kind": "text", "content": "Let me read that file."},
                {
                    "part_kind": "tool-call",
                    "tool_call_id": "tc_1",
                    "tool_name": "read_file",
                    "args": {"filepath": "/tmp/test.txt"},
                },
            ],
        }
        result = to_canonical(msg)

        assert result.role == MessageRole.ASSISTANT
        assert len(result.parts) == 2
        assert isinstance(result.parts[0], TextPart)
        assert isinstance(result.parts[1], ToolCallPart)

    def test_empty_message(self) -> None:
        """Empty dict should produce empty parts."""
        msg: dict = {}
        result = to_canonical(msg)
        assert result.parts == ()

    def test_dict_with_tool_calls_metadata(self) -> None:
        """Dict with tool_calls metadata (separate from parts).

        Some serialized messages have tool_calls as a separate key,
        not derived from parts. This can happen with failed deserialization.
        """
        msg = {
            "kind": "response",
            "parts": [],  # Empty parts
            "tool_calls": [
                {
                    "tool_call_id": "tc_meta_1",
                    "tool_name": "bash",
                    "args": {"command": "ls"},
                },
            ],
        }
        result = to_canonical(msg)

        assert result.role == MessageRole.ASSISTANT
        assert len(result.parts) == 1
        assert isinstance(result.parts[0], ToolCallPart)
        assert result.parts[0].tool_call_id == "tc_meta_1"
        assert result.parts[0].tool_name == "bash"

    def test_dict_with_tool_calls_metadata_and_parts(self) -> None:
        """Dict with both parts and tool_calls metadata.

        Should deduplicate by tool_call_id - parts take precedence.
        """
        msg = {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "tool-call",
                    "tool_call_id": "tc_1",
                    "tool_name": "from_parts",
                    "args": {"source": "parts"},
                },
            ],
            "tool_calls": [
                # Same ID as in parts - should be deduplicated
                {
                    "tool_call_id": "tc_1",
                    "tool_name": "from_metadata",
                    "args": {"source": "metadata"},
                },
                # Different ID - should be added
                {
                    "tool_call_id": "tc_2",
                    "tool_name": "only_in_metadata",
                    "args": {},
                },
            ],
        }
        result = to_canonical(msg)

        assert len(result.parts) == 2

        # First part from parts (not replaced by metadata)
        tc1 = result.parts[0]
        assert isinstance(tc1, ToolCallPart)
        assert tc1.tool_call_id == "tc_1"
        assert tc1.tool_name == "from_parts"  # Not overwritten

        # Second part from metadata
        tc2 = result.parts[1]
        assert isinstance(tc2, ToolCallPart)
        assert tc2.tool_call_id == "tc_2"
        assert tc2.tool_name == "only_in_metadata"

    def test_tool_calls_metadata_alternate_keys(self) -> None:
        """Tool calls metadata may use alternate key names."""
        msg = {
            "kind": "response",
            "parts": [],
            "tool_calls": [
                # Using 'id' instead of 'tool_call_id'
                {"id": "tc_alt_1", "name": "grep", "args": {}},
                # Using 'tool' instead of 'tool_name'
                {"tool_call_id": "tc_alt_2", "tool": "read_file", "args": {}},
            ],
        }
        result = to_canonical(msg)

        assert len(result.parts) == 2
        assert result.parts[0].tool_call_id == "tc_alt_1"
        assert result.parts[0].tool_name == "grep"
        assert result.parts[1].tool_call_id == "tc_alt_2"
        assert result.parts[1].tool_name == "read_file"


class TestFromCanonical:
    """Tests for from_canonical() conversion."""

    def test_text_message(self) -> None:
        """Convert text message back to dict."""
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(TextPart(content="Hello"),),
        )
        result = from_canonical(msg)

        assert result["kind"] == "request"
        assert len(result["parts"]) == 1
        assert result["parts"][0]["part_kind"] == "text"
        assert result["parts"][0]["content"] == "Hello"

    def test_assistant_message(self) -> None:
        """Convert assistant message back to dict."""
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(TextPart(content="I can help with that."),),
        )
        result = from_canonical(msg)

        assert result["kind"] == "response"
        assert result["parts"][0]["content"] == "I can help with that."

    def test_tool_call_message(self) -> None:
        """Convert tool call message back to dict."""
        msg = CanonicalMessage(
            role=MessageRole.ASSISTANT,
            parts=(
                ToolCallPart(
                    tool_call_id="tc_123",
                    tool_name="bash",
                    args={"command": "ls"},
                ),
            ),
        )
        result = from_canonical(msg)

        assert result["kind"] == "response"
        assert result["parts"][0]["part_kind"] == "tool-call"
        assert result["parts"][0]["tool_call_id"] == "tc_123"
        assert result["parts"][0]["tool_name"] == "bash"
        assert result["parts"][0]["args"] == {"command": "ls"}

    def test_tool_return_message(self) -> None:
        """Convert tool return message back to dict."""
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(
                ToolReturnPart(
                    tool_call_id="tc_123",
                    content="file.txt\nother.txt",
                ),
            ),
        )
        result = from_canonical(msg)

        assert result["kind"] == "request"
        assert result["parts"][0]["part_kind"] == "tool-return"
        assert result["parts"][0]["tool_call_id"] == "tc_123"
        assert result["parts"][0]["content"] == "file.txt\nother.txt"


class TestRoundTrip:
    """Tests for round-trip conversion."""

    def test_text_round_trip(self) -> None:
        """Text message round-trips correctly."""
        original = {
            "kind": "request",
            "parts": [{"part_kind": "user-prompt", "content": "Hello world"}],
        }

        canonical = to_canonical(original)
        restored = from_canonical(canonical)

        # Content should be preserved (structure may differ slightly)
        assert restored["kind"] == "request"
        assert restored["parts"][0]["content"] == "Hello world"

    def test_tool_call_round_trip(self) -> None:
        """Tool call round-trips correctly."""
        original = {
            "kind": "response",
            "parts": [
                {
                    "part_kind": "tool-call",
                    "tool_call_id": "tc_abc",
                    "tool_name": "read_file",
                    "args": {"filepath": "/path/to/file"},
                }
            ],
        }

        canonical = to_canonical(original)
        restored = from_canonical(canonical)

        assert restored["parts"][0]["tool_call_id"] == "tc_abc"
        assert restored["parts"][0]["tool_name"] == "read_file"
        assert restored["parts"][0]["args"] == {"filepath": "/path/to/file"}


class TestGetContentParity:
    """Tests verifying get_content() matches legacy get_message_content()."""

    @pytest.mark.parametrize(
        "message",
        [
            {"content": "Simple content"},
            {"thought": "A thought"},
            {"content": "Multiple", "other": "ignored"},
        ],
    )
    def test_dict_parity(self, message: dict) -> None:
        """get_content() should match get_message_content() for dicts."""
        legacy_result = get_message_content(message)
        new_result = get_content(message)
        assert new_result == legacy_result

    def test_canonical_message(self) -> None:
        """get_content() works directly on CanonicalMessage."""
        msg = CanonicalMessage(
            role=MessageRole.USER,
            parts=(TextPart(content="Direct access"),),
        )
        assert get_content(msg) == "Direct access"


class TestToolCallHelpers:
    """Tests for tool call ID extraction helpers."""

    def test_get_tool_call_ids_from_dict(self) -> None:
        """Extract tool call IDs from dict message."""
        msg = {
            "kind": "response",
            "parts": [
                {"part_kind": "tool-call", "tool_call_id": "tc_1", "tool_name": "a", "args": {}},
                {"part_kind": "tool-call", "tool_call_id": "tc_2", "tool_name": "b", "args": {}},
            ],
        }
        assert get_tool_call_ids(msg) == {"tc_1", "tc_2"}

    def test_get_tool_return_ids_from_dict(self) -> None:
        """Extract tool return IDs from dict message."""
        msg = {
            "kind": "request",
            "parts": [
                {"part_kind": "tool-return", "tool_call_id": "tc_1", "content": "result"},
            ],
        }
        assert get_tool_return_ids(msg) == {"tc_1"}

    def test_find_dangling_tool_calls(self) -> None:
        """Find tool calls without matching returns."""
        tool_call_1 = {
            "part_kind": "tool-call",
            "tool_call_id": "tc_1",
            "tool_name": "a",
            "args": {},
        }
        tool_call_2 = {
            "part_kind": "tool-call",
            "tool_call_id": "tc_2",
            "tool_name": "b",
            "args": {},
        }
        messages = [
            {"kind": "response", "parts": [tool_call_1, tool_call_2]},
            {
                "kind": "request",
                "parts": [
                    {"part_kind": "tool-return", "tool_call_id": "tc_1", "content": "done"},
                ],
            },
        ]

        dangling = find_dangling_tool_calls(messages)
        assert dangling == {"tc_2"}  # tc_2 has no return

    def test_find_dangling_no_dangling(self) -> None:
        """No dangling when all calls have returns."""
        tool_call = {
            "part_kind": "tool-call",
            "tool_call_id": "tc_1",
            "tool_name": "a",
            "args": {},
        }
        messages = [
            {"kind": "response", "parts": [tool_call]},
            {
                "kind": "request",
                "parts": [
                    {"part_kind": "tool-return", "tool_call_id": "tc_1", "content": "done"},
                ],
            },
        ]

        dangling = find_dangling_tool_calls(messages)
        assert dangling == set()

    def test_find_dangling_from_tool_calls_metadata(self) -> None:
        """Find dangling tool calls from tool_calls metadata."""
        messages = [
            {
                "kind": "response",
                "parts": [],  # No parts
                "tool_calls": [
                    {"tool_call_id": "tc_meta_1", "tool_name": "bash", "args": {}},
                    {"tool_call_id": "tc_meta_2", "tool_name": "grep", "args": {}},
                ],
            },
            {
                "kind": "request",
                "parts": [
                    {"part_kind": "tool-return", "tool_call_id": "tc_meta_1", "content": "ok"},
                ],
            },
        ]

        dangling = find_dangling_tool_calls(messages)
        assert dangling == {"tc_meta_2"}  # tc_meta_2 has no return

    def test_get_tool_call_ids_from_metadata(self) -> None:
        """Extract tool call IDs from tool_calls metadata."""
        msg = {
            "kind": "response",
            "parts": [],
            "tool_calls": [
                {"tool_call_id": "tc_m1", "tool_name": "a", "args": {}},
                {"id": "tc_m2", "name": "b", "args": {}},  # Alternate key names
            ],
        }
        assert get_tool_call_ids(msg) == {"tc_m1", "tc_m2"}
