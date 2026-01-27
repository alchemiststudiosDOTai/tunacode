"""Tests for multi-strategy fallback tool parser.

Tests parsing of non-standard tool calling formats from models like Qwen2.5-Coder.
"""

import json

import pytest

import tunacode.tools.parsing.tool_parser as tool_parser
from tunacode.tools.parsing.tool_parser import (
    ParseDiagnostics,
    ParsedToolCall,
    _normalize_tool_object,
    has_potential_tool_call,
    parse_code_fence,
    parse_hermes_style,
    parse_qwen2_xml,
    parse_raw_json,
    parse_tool_calls_from_text,
)

TOOL_NAME = "read_file"
INVALID_JSON_ARGS = "{invalid}"
INVALID_TOOL_OBJECT = {"name": TOOL_NAME, "arguments": INVALID_JSON_ARGS}
INVALID_LIST_ARGS = ["nope"]
INVALID_LIST_OBJECT = {"name": TOOL_NAME, "arguments": INVALID_LIST_ARGS}
TOOL_CALL_ARGS = {"filepath": "main.py"}
TOOL_CALL_TEXT = json.dumps({"name": TOOL_NAME, "arguments": TOOL_CALL_ARGS})
TOOL_CALL_WRAPPED = f"<tool_call>{TOOL_CALL_TEXT}</tool_call>"
HERMES_INVALID_TEXT = f"<function={TOOL_NAME}>{INVALID_JSON_ARGS}</function>"
DIAGNOSTIC_STRATEGY_NAME = "example"
DIAGNOSTIC_FAILURE_REASON = "failed"
DIAGNOSTIC_ERROR_MESSAGE = "boom"
EXPECTED_INDICATOR = "<tool_call>"
SUCCESS_LABEL = "SUCCESS"
FAILED_LABEL = "FAILED"
ERROR_LABEL = "error"
PRE_CHECK_LABEL = "pre-check"
EMPTY_TEXT_REASON = "empty_text"
EMPTY_TEXT = " "


class TestQwen2XmlParsing:
    """Tests for Qwen2-style XML tool call parsing."""

    def test_single_tool_call(self):
        """Parse single Qwen2-style tool call."""
        text = (
            '<tool_call>{"name": "read_file", '
            '"arguments": {"filepath": "/path/to/file.py"}}</tool_call>'
        )
        result = parse_qwen2_xml(text)

        assert result is not None
        assert len(result) == 1
        assert result[0].tool_name == "read_file"
        assert result[0].args == {"filepath": "/path/to/file.py"}
        assert result[0].tool_call_id  # Should have generated ID

    def test_multiple_tool_calls(self):
        """Parse multiple Qwen2-style tool calls in same text."""
        text = """
        <tool_call>{"name": "read_file", "arguments": {"filepath": "/a.py"}}</tool_call>
        Some text between calls
        <tool_call>{"name": "grep", "arguments": {"pattern": "def"}}</tool_call>
        """
        result = parse_qwen2_xml(text)

        assert result is not None
        assert len(result) == 2
        assert result[0].tool_name == "read_file"
        assert result[1].tool_name == "grep"

    def test_tool_call_with_whitespace(self):
        """Parse tool call with various whitespace."""
        text = """<tool_call>
            {
                "name": "bash",
                "arguments": {"command": "ls -la"}
            }
        </tool_call>"""
        result = parse_qwen2_xml(text)

        assert result is not None
        assert len(result) == 1
        assert result[0].tool_name == "bash"

    def test_no_tool_call_returns_none(self):
        """Return None when no tool calls found."""
        text = "Just some regular text without any tool calls."
        result = parse_qwen2_xml(text)

        assert result is None

    def test_malformed_json_skipped(self):
        """Skip tool calls with malformed JSON."""
        text = '<tool_call>{"name": "broken", "arguments": {invalid}}</tool_call>'
        result = parse_qwen2_xml(text)

        assert result is None


class TestHermesStyleParsing:
    """Tests for Hermes-style function call parsing."""

    def test_single_function_call(self):
        """Parse single Hermes-style function call."""
        text = '<function=read_file>{"filepath": "/path/to/file.py"}</function>'
        result = parse_hermes_style(text)

        assert result is not None
        assert len(result) == 1
        assert result[0].tool_name == "read_file"
        assert result[0].args == {"filepath": "/path/to/file.py"}

    def test_multiple_function_calls(self):
        """Parse multiple Hermes-style function calls."""
        text = """
        <function=grep>{"pattern": "TODO"}</function>
        <function=read_file>{"filepath": "main.py"}</function>
        """
        result = parse_hermes_style(text)

        assert result is not None
        assert len(result) == 2

    def test_no_match_returns_none(self):
        """Return None when no function tags found."""
        text = "Regular text <not_function>data</not_function>"
        result = parse_hermes_style(text)

        assert result is None


class TestCodeFenceParsing:
    """Tests for code fence JSON parsing."""

    def test_json_code_fence(self):
        """Parse JSON inside ```json fence."""
        text = """```json
{"name": "write_file", "arguments": {"filepath": "test.py", "content": "print('hello')"}}
```"""
        result = parse_code_fence(text)

        assert result is not None
        assert len(result) == 1
        assert result[0].tool_name == "write_file"

    def test_plain_code_fence(self):
        """Parse JSON inside plain ``` fence."""
        text = """```
{"name": "bash", "arguments": {"command": "echo test"}}
```"""
        result = parse_code_fence(text)

        assert result is not None
        assert len(result) == 1

    def test_non_tool_json_skipped(self):
        """Skip JSON that doesn't look like a tool call."""
        text = """```json
{"data": "just some data", "not_a_tool": true}
```"""
        result = parse_code_fence(text)

        assert result is None


class TestRawJsonParsing:
    """Tests for raw JSON tool call parsing."""

    def test_embedded_json_tool_call(self):
        """Parse raw JSON tool call embedded in text."""
        text = """I'll read the file for you:
{"name": "read_file", "arguments": {"filepath": "main.py"}}
Let me check that."""
        result = parse_raw_json(text)

        assert result is not None
        assert len(result) == 1
        assert result[0].tool_name == "read_file"

    def test_alternative_format_tool_args(self):
        """Parse {"tool": ..., "args": ...} format."""
        text = '{"tool": "grep", "args": {"pattern": "import"}}'
        result = parse_raw_json(text)

        assert result is not None
        assert len(result) == 1
        assert result[0].tool_name == "grep"


class TestMainParser:
    """Tests for the main parse_tool_calls_from_text function."""

    def test_qwen2_format_parsed(self):
        """Main parser handles Qwen2 format."""
        text = '<tool_call>{"name": "read_file", "arguments": {"filepath": "test.py"}}</tool_call>'
        result = parse_tool_calls_from_text(text)

        assert len(result) == 1
        assert result[0].tool_name == "read_file"

    def test_hermes_format_parsed(self):
        """Main parser handles Hermes format."""
        text = '<function=bash>{"command": "pwd"}</function>'
        result = parse_tool_calls_from_text(text)

        assert len(result) == 1
        assert result[0].tool_name == "bash"

    def test_empty_text_returns_empty_list(self):
        """Empty text returns empty list, not None."""
        assert parse_tool_calls_from_text("") == []
        assert parse_tool_calls_from_text("   ") == []

    def test_no_tool_calls_returns_empty_list(self):
        """Text without tool calls returns empty list."""
        result = parse_tool_calls_from_text("Just regular conversation text.")
        assert result == []

    def test_strategy_priority(self):
        """More specific strategies tried first."""
        # This text could match multiple strategies
        text = '<tool_call>{"name": "read_file", "arguments": {}}</tool_call>'
        result = parse_tool_calls_from_text(text)

        # Should use qwen2_xml (first in priority)
        assert len(result) == 1


class TestHasPotentialToolCall:
    """Tests for the quick-check function."""

    def test_qwen2_indicator(self):
        """Detect Qwen2 tool_call tag."""
        assert has_potential_tool_call("<tool_call>") is True

    def test_hermes_indicator(self):
        """Detect Hermes function tag."""
        assert has_potential_tool_call("<function=test>") is True

    def test_json_name_indicator(self):
        """Detect JSON name key."""
        assert has_potential_tool_call('{"name": "read"}') is True

    def test_code_fence_indicator(self):
        """Detect code fence."""
        assert has_potential_tool_call("```json") is True

    def test_no_indicators(self):
        """Return False when no indicators."""
        assert has_potential_tool_call("Regular text") is False

    def test_empty_text(self):
        """Return False for empty text."""
        assert has_potential_tool_call("") is False
        assert has_potential_tool_call(None) is False


class TestNormalizeToolObject:
    """Tests for tool object normalization."""

    def test_name_arguments_format(self):
        """Normalize {"name": ..., "arguments": ...} format."""
        obj = {"name": "read_file", "arguments": {"filepath": "test.py"}}
        result = _normalize_tool_object(obj)

        assert result is not None
        assert result.tool_name == "read_file"
        assert result.args == {"filepath": "test.py"}

    def test_tool_args_format(self):
        """Normalize {"tool": ..., "args": ...} format."""
        obj = {"tool": "bash", "args": {"command": "ls"}}
        result = _normalize_tool_object(obj)

        assert result is not None
        assert result.tool_name == "bash"
        assert result.args == {"command": "ls"}

    def test_function_parameters_format(self):
        """Normalize {"function": ..., "parameters": ...} format."""
        obj = {"function": "grep", "parameters": {"pattern": "test"}}
        result = _normalize_tool_object(obj)

        assert result is not None
        assert result.tool_name == "grep"
        assert result.args == {"pattern": "test"}

    def test_string_args_parsed(self):
        """Parse string arguments as JSON."""
        obj = {"name": "test", "arguments": '{"key": "value"}'}
        result = _normalize_tool_object(obj)

        assert result is not None
        assert result.args == {"key": "value"}

    def test_missing_name_returns_none(self):
        """Return None when no tool name found."""
        obj = {"arguments": {"key": "value"}}
        result = _normalize_tool_object(obj)

        assert result is None

    def test_non_dict_returns_none(self):
        """Return None for non-dict input."""
        assert _normalize_tool_object("string") is None
        assert _normalize_tool_object(None) is None
        assert _normalize_tool_object([]) is None


class TestParsedToolCallDataclass:
    """Tests for ParsedToolCall dataclass."""

    def test_immutable(self):
        """ParsedToolCall is frozen (immutable)."""
        call = ParsedToolCall(tool_name="test", args={"key": "value"}, tool_call_id="test-id")

        with pytest.raises(AttributeError):
            call.tool_name = "changed"

    def test_slots_optimization(self):
        """ParsedToolCall uses slots for memory efficiency."""
        call = ParsedToolCall(tool_name="test", args={}, tool_call_id="id")

        # Slots means no __dict__
        with pytest.raises(AttributeError):
            _ = call.__dict__


class TestParseDiagnostics:
    """Tests for ParseDiagnostics formatting and branches."""

    def test_format_for_debug_success_includes_success_label(self):
        """format_for_debug includes success line when parsing succeeds."""
        diagnostics = ParseDiagnostics(
            text_preview=TOOL_CALL_WRAPPED,
            text_length=len(TOOL_CALL_WRAPPED),
            detected_indicators=[EXPECTED_INDICATOR],
            strategies_tried=[(DIAGNOSTIC_STRATEGY_NAME, DIAGNOSTIC_FAILURE_REASON)],
            success=True,
            success_strategy=DIAGNOSTIC_STRATEGY_NAME,
        )

        formatted = diagnostics.format_for_debug()

        assert SUCCESS_LABEL in formatted
        assert DIAGNOSTIC_STRATEGY_NAME in formatted

    def test_format_for_debug_failure_includes_failed_label(self):
        """format_for_debug includes failure line when parsing fails."""
        diagnostics = ParseDiagnostics(
            text_preview=TOOL_CALL_WRAPPED,
            text_length=len(TOOL_CALL_WRAPPED),
            detected_indicators=[EXPECTED_INDICATOR],
            strategies_tried=[(DIAGNOSTIC_STRATEGY_NAME, DIAGNOSTIC_FAILURE_REASON)],
            success=False,
            success_strategy=None,
        )

        formatted = diagnostics.format_for_debug()

        assert FAILED_LABEL in formatted


class TestHermesErrorHandling:
    """Tests Hermes parser error paths."""

    def test_invalid_json_is_skipped(self):
        """Invalid JSON inside Hermes tags is skipped."""
        result = parse_hermes_style(HERMES_INVALID_TEXT)

        assert result is None


class TestNormalizeToolObjectEdgeCases:
    """Tests for argument normalization branches."""

    def test_invalid_string_args_return_empty_dict(self):
        """Invalid JSON argument strings normalize to empty dict."""
        parsed = _normalize_tool_object(INVALID_TOOL_OBJECT)

        assert parsed is not None
        assert parsed.args == {}

    def test_non_string_args_return_empty_dict(self):
        """Non-string, non-dict arguments normalize to empty dict."""
        parsed = _normalize_tool_object(INVALID_LIST_OBJECT)

        assert parsed is not None
        assert parsed.args == {}


class TestParseToolCallsWithDiagnostics:
    """Tests diagnostics paths for parse_tool_calls_from_text."""

    def test_empty_text_returns_diagnostics(self):
        """Empty text with diagnostics returns pre-check entry."""
        results, diagnostics = parse_tool_calls_from_text(EMPTY_TEXT, collect_diagnostics=True)

        assert results == []
        assert diagnostics.strategies_tried == [(PRE_CHECK_LABEL, EMPTY_TEXT_REASON)]

    def test_successful_parse_records_diagnostics(self):
        """Successful parse sets diagnostics success fields."""
        results, diagnostics = parse_tool_calls_from_text(
            TOOL_CALL_WRAPPED, collect_diagnostics=True
        )

        assert results
        assert diagnostics.success is True
        assert diagnostics.success_strategy is not None
        assert diagnostics.detected_indicators

    def test_strategy_errors_reported_in_diagnostics(self, monkeypatch: pytest.MonkeyPatch):
        """Errors in strategies are recorded and diagnostics returned."""

        def _boom(_: str) -> list[ParsedToolCall] | None:
            raise ValueError(DIAGNOSTIC_ERROR_MESSAGE)

        monkeypatch.setattr(
            tool_parser,
            "PARSING_STRATEGIES",
            [(DIAGNOSTIC_STRATEGY_NAME, _boom)],
        )

        results, diagnostics = parse_tool_calls_from_text(
            TOOL_CALL_WRAPPED, collect_diagnostics=True
        )

        assert results == []
        assert isinstance(diagnostics, ParseDiagnostics)  # type: ignore[union-attr]
        assert diagnostics.success is False  # type: ignore[union-attr]
        assert diagnostics.strategies_tried  # type: ignore[union-attr]
        assert ERROR_LABEL in diagnostics.strategies_tried[0][1]  # type: ignore[union-attr]
