"""Tests for tunacode.core.agents.resume.sanitize_debug."""

from types import SimpleNamespace

from tunacode.core.agents.resume.sanitize_debug import (
    DEBUG_NEWLINE_REPLACEMENT,
    DEBUG_PREVIEW_SUFFIX,
    _format_debug_preview,
    _format_part_debug,
    _format_tool_call_debug,
)


class TestFormatDebugPreview:
    def test_none_returns_empty(self):
        text, length = _format_debug_preview(None, 100)
        assert text == ""
        assert length == 0

    def test_short_string_returned_as_is(self):
        text, length = _format_debug_preview("hello", 100)
        assert text == "hello"
        assert length == 5

    def test_exact_max_len_no_suffix(self):
        value = "abcde"
        text, length = _format_debug_preview(value, 5)
        assert text == "abcde"
        assert length == 5
        assert DEBUG_PREVIEW_SUFFIX not in text

    def test_long_string_truncated_with_suffix(self):
        value = "a" * 50
        max_len = 10
        text, length = _format_debug_preview(value, max_len)
        assert text == "a" * 10 + DEBUG_PREVIEW_SUFFIX
        assert length == 50

    def test_newlines_replaced(self):
        value = "line1\nline2"
        text, length = _format_debug_preview(value, 100)
        assert "\n" not in text
        assert DEBUG_NEWLINE_REPLACEMENT in text
        assert length == 11

    def test_long_string_with_newlines(self):
        value = "abc\ndef\nghi"
        text, length = _format_debug_preview(value, 5)
        # Truncated to 5 chars: "abc\nd", then newline replaced, then suffix added
        assert DEBUG_PREVIEW_SUFFIX in text
        assert "\n" not in text
        assert length == 11

    def test_non_string_value_converted(self):
        text, length = _format_debug_preview(42, 100)
        assert text == "42"
        assert length == 2

    def test_empty_string(self):
        text, length = _format_debug_preview("", 100)
        assert text == ""
        assert length == 0


class TestFormatPartDebug:
    def test_part_with_kind_tool_name_content(self):
        part = SimpleNamespace(
            part_kind="tool-call",
            tool_name="bash",
            tool_call_id="tc_123",
            content="echo hello",
            args=None,
        )
        result = _format_part_debug(part, 120)
        assert "kind=tool-call" in result
        assert "tool=bash" in result
        assert "id=tc_123" in result
        assert "content=echo hello" in result

    def test_part_with_no_tool_info(self):
        part = SimpleNamespace(
            part_kind="text",
            tool_name=None,
            tool_call_id=None,
            content="just text",
            args=None,
        )
        result = _format_part_debug(part, 120)
        assert "kind=text" in result
        assert "tool=" not in result
        assert "id=" not in result
        assert "content=just text" in result

    def test_part_with_args(self):
        part = SimpleNamespace(
            part_kind="tool-call",
            tool_name="write",
            tool_call_id="tc_456",
            content=None,
            args='{"path": "/tmp/test.txt"}',
        )
        result = _format_part_debug(part, 120)
        assert "kind=tool-call" in result
        assert "args=" in result
        assert "content=" not in result

    def test_part_with_unknown_kind(self):
        part = SimpleNamespace(
            tool_name=None,
            tool_call_id=None,
            content=None,
            args=None,
        )
        # part_kind is missing, _get_attr returns None, so "unknown" is used
        result = _format_part_debug(part, 120)
        assert "kind=unknown" in result

    def test_part_with_empty_content(self):
        part = SimpleNamespace(
            part_kind="text",
            tool_name=None,
            tool_call_id=None,
            content="",
            args=None,
        )
        result = _format_part_debug(part, 120)
        assert "kind=text" in result
        # Empty content returns ("", 0) from _format_debug_preview, so content is not appended
        assert "content=" not in result


class TestFormatToolCallDebug:
    def test_tool_call_with_name_id_args(self):
        tool_call = SimpleNamespace(
            tool_name="bash",
            tool_call_id="tc_789",
            args='{"command": "ls"}',
        )
        result = _format_tool_call_debug(tool_call, 120)
        assert "tool=bash" in result
        assert "id=tc_789" in result
        assert "args=" in result

    def test_tool_call_with_name_only(self):
        tool_call = SimpleNamespace(
            tool_name="read",
            tool_call_id=None,
            args=None,
        )
        result = _format_tool_call_debug(tool_call, 120)
        assert "tool=read" in result
        assert "id=" not in result
        assert "args=" not in result

    def test_empty_tool_call_returns_empty_label(self):
        tool_call = SimpleNamespace(
            tool_name=None,
            tool_call_id=None,
            args=None,
        )
        result = _format_tool_call_debug(tool_call, 120)
        assert result == "empty"

    def test_tool_call_long_args_truncated(self):
        long_args = "x" * 200
        tool_call = SimpleNamespace(
            tool_name="write",
            tool_call_id="tc_001",
            args=long_args,
        )
        result = _format_tool_call_debug(tool_call, 50)
        assert DEBUG_PREVIEW_SUFFIX in result
        assert "200 chars" in result

    def test_tool_call_with_id_no_name(self):
        tool_call = SimpleNamespace(
            tool_name=None,
            tool_call_id="tc_orphan",
            args=None,
        )
        result = _format_tool_call_debug(tool_call, 120)
        assert "id=tc_orphan" in result
        assert "tool=" not in result
