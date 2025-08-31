"""Unit tests for the OpenAI formatter."""

import json

import pytest

from tunacode.tools.openai_formatter import OpenAIFormatter


class TestOpenAIFormatter:
    """Test cases for OpenAI function call formatting."""

    def test_format_tool_call_basic(self):
        """Test basic tool call formatting."""
        result = OpenAIFormatter.format_tool_call("test_tool", {"arg1": "value1", "arg2": 42})

        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 1

        call = result["tool_calls"][0]
        assert call["type"] == "function"
        assert call["function"]["name"] == "test_tool"

        # Arguments should be stringified JSON
        args = json.loads(call["function"]["arguments"])
        assert args == {"arg1": "value1", "arg2": 42}

    def test_format_multiple_tool_calls(self):
        """Test formatting multiple tool calls."""
        calls = [("tool1", {"param": "value1"}), ("tool2", {"param": "value2"})]

        result = OpenAIFormatter.format_multiple_tool_calls(calls)

        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 2

        # Check first call
        call1 = result["tool_calls"][0]
        assert call1["function"]["name"] == "tool1"
        args1 = json.loads(call1["function"]["arguments"])
        assert args1 == {"param": "value1"}

        # Check second call
        call2 = result["tool_calls"][1]
        assert call2["function"]["name"] == "tool2"
        args2 = json.loads(call2["function"]["arguments"])
        assert args2 == {"param": "value2"}

    def test_parse_tool_response(self):
        """Test parsing OpenAI format response back to dict."""
        # Create a response in OpenAI format
        response_data = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "test_tool", "arguments": json.dumps({"arg": "value"})},
                }
            ]
        }

        response_json = json.dumps(response_data)
        parsed = OpenAIFormatter.parse_tool_response(response_json)

        assert "tool_calls" in parsed
        call = parsed["tool_calls"][0]
        assert call["function"]["name"] == "test_tool"
        # Arguments should be parsed back to dict
        assert call["function"]["arguments"] == {"arg": "value"}

    def test_validate_format_valid(self):
        """Test validation of valid OpenAI format."""
        valid_data = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "test_tool", "arguments": json.dumps({"arg": "value"})},
                }
            ]
        }

        assert OpenAIFormatter.validate_format(valid_data) is True

    def test_validate_format_invalid_missing_tool_calls(self):
        """Test validation fails when tool_calls is missing."""
        invalid_data = {"other_field": "value"}
        assert OpenAIFormatter.validate_format(invalid_data) is False

    def test_validate_format_invalid_wrong_type(self):
        """Test validation fails when type is not 'function'."""
        invalid_data = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "other_type",
                    "function": {"name": "test_tool", "arguments": json.dumps({"arg": "value"})},
                }
            ]
        }

        assert OpenAIFormatter.validate_format(invalid_data) is False

    def test_validate_format_invalid_non_string_arguments(self):
        """Test validation fails when arguments are not stringified."""
        invalid_data = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "arguments": {"arg": "value"},  # Should be string, not dict
                    },
                }
            ]
        }

        assert OpenAIFormatter.validate_format(invalid_data) is False

    def test_validate_format_invalid_missing_fields(self):
        """Test validation fails when required fields are missing."""
        invalid_data = {
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    # Missing function field
                }
            ]
        }

        assert OpenAIFormatter.validate_format(invalid_data) is False

    def test_format_preserves_argument_types(self):
        """Test that argument types are preserved through stringify/parse cycle."""
        original_args = {
            "string_arg": "text",
            "int_arg": 42,
            "float_arg": 3.14,
            "bool_arg": True,
            "null_arg": None,
            "list_arg": [1, 2, 3],
            "dict_arg": {"nested": "value"},
        }

        # Format -> stringify -> parse cycle
        formatted = OpenAIFormatter.format_tool_call("test", original_args)
        response_json = json.dumps(formatted)
        parsed = OpenAIFormatter.parse_tool_response(response_json)

        recovered_args = parsed["tool_calls"][0]["function"]["arguments"]
        assert recovered_args == original_args


if __name__ == "__main__":
    pytest.main([__file__])
