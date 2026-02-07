"""Tests for tunacode.core.agents.agent_components.orchestrator.debug_format."""

from types import SimpleNamespace

from tunacode.core.agents.agent_components.orchestrator.debug_format import (
    PART_PREVIEW_LENGTH,
    format_part,
    format_preview,
    format_tool_return,
)
from tunacode.core.agents.resume.sanitize_debug import DEBUG_PREVIEW_SUFFIX


class TestFormatPreview:
    def test_none_returns_empty(self):
        preview, length = format_preview(None)
        assert preview == ""
        assert length == 0

    def test_short_string(self):
        preview, length = format_preview("hello")
        assert preview == "hello"
        assert length == 5

    def test_long_string_truncated_with_suffix(self):
        overflow = 50
        text = "a" * (PART_PREVIEW_LENGTH + overflow)
        preview, length = format_preview(text)
        assert preview.startswith("a" * PART_PREVIEW_LENGTH)
        assert preview.endswith(DEBUG_PREVIEW_SUFFIX)
        assert length == PART_PREVIEW_LENGTH + overflow

    def test_exact_boundary_no_suffix(self):
        text = "b" * PART_PREVIEW_LENGTH
        preview, length = format_preview(text)
        assert DEBUG_PREVIEW_SUFFIX not in preview
        assert length == PART_PREVIEW_LENGTH

    def test_int_value_converted(self):
        preview, length = format_preview(42)
        assert preview == "42"
        assert length == 2

    def test_newlines_replaced(self):
        text = "line1\nline2"
        preview, _length = format_preview(text)
        assert "\n" not in preview
        assert "\\n" in preview


class TestFormatPart:
    def test_text_part(self):
        part = SimpleNamespace(part_kind="text", content="hello", args=None)
        result = format_part(part)
        assert "kind=text" in result
        assert "content=hello" in result

    def test_tool_call_part(self):
        part = SimpleNamespace(
            part_kind="tool-call",
            tool_name="read_file",
            tool_call_id="id_456",
            content=None,
            args='{"file_path": "/tmp/x.py"}',
        )
        result = format_part(part)
        assert "kind=tool-call" in result
        assert "tool=read_file" in result
        assert "id=id_456" in result
        assert "args=" in result

    def test_unknown_kind(self):
        part = SimpleNamespace(content="data", args=None)
        result = format_part(part)
        assert "kind=unknown" in result

    def test_no_content_no_args(self):
        part = SimpleNamespace(part_kind="system", content=None, args=None)
        result = format_part(part)
        assert result == "kind=system"


class TestFormatToolReturn:
    def test_with_all_fields(self):
        result = format_tool_return(
            tool_name="grep",
            tool_call_id="call_789",
            tool_args='{"pattern": "TODO"}',
            content="found 3 matches",
        )
        assert result.startswith("Tool return sent:")
        assert "tool=grep" in result
        assert "id=call_789" in result
        assert "args=" in result
        assert "result=" in result

    def test_without_tool_call_id(self):
        result = format_tool_return(
            tool_name="bash",
            tool_call_id=None,
            tool_args='{"cmd": "ls"}',
            content="output",
        )
        assert "tool=bash" in result
        assert "id=" not in result

    def test_long_args_truncated(self):
        args_length = PART_PREVIEW_LENGTH * 2
        long_args = "z" * args_length
        result = format_tool_return(
            tool_name="edit",
            tool_call_id="c1",
            tool_args=long_args,
            content="ok",
        )
        assert DEBUG_PREVIEW_SUFFIX in result
        assert str(args_length) in result

    def test_none_content(self):
        result = format_tool_return(
            tool_name="bash",
            tool_call_id=None,
            tool_args=None,
            content=None,
        )
        assert "tool=bash" in result
        assert "result=" not in result
