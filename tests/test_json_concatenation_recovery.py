"""Tests for JSON concatenation recovery functionality."""

import json
from unittest.mock import Mock, patch

import pytest

from tunacode.cli.repl_components.command_parser import parse_args
from tunacode.cli.repl_components.error_recovery import (
    attempt_json_args_recovery,
    attempt_tool_recovery,
)
from tunacode.exceptions import ValidationError
from tunacode.utils.json_utils import (
    ConcatenatedJSONError,
    safe_json_parse,
    split_concatenated_json,
    validate_tool_args_safety,
)


class TestSplitConcatenatedJson:
    """Test the split_concatenated_json function."""

    def test_single_valid_json(self):
        """Test splitting single valid JSON object."""
        json_str = '{"name": "test", "value": 42}'
        result = split_concatenated_json(json_str)
        assert len(result) == 1
        assert result[0] == {"name": "test", "value": 42}

    def test_two_concatenated_objects(self):
        """Test splitting two concatenated JSON objects."""
        json_str = '{"name": "first"}{"name": "second"}'
        result = split_concatenated_json(json_str)
        assert len(result) == 2
        assert result[0] == {"name": "first"}
        assert result[1] == {"name": "second"}

    def test_three_concatenated_objects(self):
        """Test splitting three concatenated JSON objects."""
        json_str = '{"a": 1}{"b": 2}{"c": 3}'
        result = split_concatenated_json(json_str)
        assert len(result) == 3
        assert result[0] == {"a": 1}
        assert result[1] == {"b": 2}
        assert result[2] == {"c": 3}

    def test_nested_objects(self):
        """Test splitting concatenated objects with nesting."""
        json_str = '{"data": {"nested": true}}{"simple": "value"}'
        result = split_concatenated_json(json_str)
        assert len(result) == 2
        assert result[0] == {"data": {"nested": True}}
        assert result[1] == {"simple": "value"}

    def test_objects_with_strings_containing_braces(self):
        """Test objects containing strings with braces."""
        json_str = '{"message": "Hello {world}"}{"code": "if (x) { return; }"}'
        result = split_concatenated_json(json_str)
        assert len(result) == 2
        assert result[0] == {"message": "Hello {world}"}
        assert result[1] == {"code": "if (x) { return; }"}

    def test_objects_with_escaped_quotes(self):
        """Test objects with escaped quotes."""
        json_str = '{"text": "He said \\"Hello\\""}{"response": "She replied \\"Hi\\""}'
        result = split_concatenated_json(json_str)
        assert len(result) == 2
        assert result[0] == {"text": 'He said "Hello"'}
        assert result[1] == {"response": 'She replied "Hi"'}

    def test_invalid_json_skipped(self):
        """Test that invalid JSON fragments are skipped."""
        json_str = '{"valid": true}{invalid json}{"also_valid": false}'
        result = split_concatenated_json(json_str)
        assert len(result) == 2
        assert result[0] == {"valid": True}
        assert result[1] == {"also_valid": False}

    def test_no_valid_json_raises_error(self):
        """Test that no valid JSON raises JSONDecodeError."""
        json_str = "{invalid}{also invalid}"
        with pytest.raises(json.JSONDecodeError):
            split_concatenated_json(json_str)

    def test_empty_string_raises_error(self):
        """Test that empty string raises JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            split_concatenated_json("")

    def test_whitespace_handling(self):
        """Test handling of whitespace between objects."""
        json_str = '  {"first": 1}   {"second": 2}  '
        result = split_concatenated_json(json_str)
        assert len(result) == 2
        assert result[0] == {"first": 1}
        assert result[1] == {"second": 2}


class TestValidateToolArgsSafety:
    """Test the validate_tool_args_safety function."""

    def test_single_object_always_safe(self):
        """Test that single objects are always safe."""
        objects = [{"arg": "value"}]
        assert validate_tool_args_safety(objects, "any_tool") is True

    def test_empty_list_always_safe(self):
        """Test that empty list is always safe."""
        assert validate_tool_args_safety([], "any_tool") is True

    def test_read_only_tool_multiple_objects_safe(self):
        """Test that read-only tools can handle multiple objects."""
        objects = [{"file": "a.py"}, {"file": "b.py"}]
        # Assuming "read_file" is in READ_ONLY_TOOLS
        assert validate_tool_args_safety(objects, "read_file") is True

    def test_write_tool_multiple_objects_unsafe(self):
        """Test that write tools with multiple objects raise error."""
        objects = [{"file": "a.py", "content": "..."}, {"file": "b.py", "content": "..."}]
        with pytest.raises(ConcatenatedJSONError) as exc_info:
            validate_tool_args_safety(objects, "write_file")

        assert exc_info.value.objects_found == 2
        assert exc_info.value.tool_name == "write_file"

    def test_unknown_tool_multiple_objects_unsafe(self):
        """Test that unknown tools with multiple objects raise error."""
        objects = [{"arg1": "value1"}, {"arg2": "value2"}]
        with pytest.raises(ConcatenatedJSONError) as exc_info:
            validate_tool_args_safety(objects, "unknown_tool")

        assert exc_info.value.objects_found == 2
        assert exc_info.value.tool_name == "unknown_tool"

    def test_no_tool_name_multiple_objects_unsafe(self):
        """Test that multiple objects with no tool name return False."""
        objects = [{"arg1": "value1"}, {"arg2": "value2"}]
        assert validate_tool_args_safety(objects, None) is False


class TestSafeJsonParse:
    """Test the safe_json_parse function."""

    def test_normal_json_parsing(self):
        """Test normal JSON parsing works as expected."""
        json_str = '{"name": "test", "value": 42}'
        result = safe_json_parse(json_str)
        assert result == {"name": "test", "value": 42}

    def test_concatenated_not_allowed_raises_error(self):
        """Test that concatenated JSON raises error when not allowed."""
        json_str = '{"first": 1}{"second": 2}'
        with pytest.raises(json.JSONDecodeError):
            safe_json_parse(json_str, allow_concatenated=False)

    def test_concatenated_allowed_returns_first(self):
        """Test that concatenated JSON returns first object when allowed."""
        json_str = '{"first": 1}{"second": 2}'
        result = safe_json_parse(json_str, allow_concatenated=True)
        assert result == {"first": 1}

    def test_concatenated_read_only_tool_returns_list(self):
        """Test that concatenated JSON for read-only tools returns list."""
        json_str = '{"file": "a.py"}{"file": "b.py"}'
        result = safe_json_parse(json_str, tool_name="read_file", allow_concatenated=True)
        # Should return list for read-only tools
        expected = [{"file": "a.py"}, {"file": "b.py"}]
        assert result == expected

    def test_invalid_json_type_raises_error(self):
        """Test that non-dict JSON types raise error."""
        json_str = '"just a string"'
        with pytest.raises(json.JSONDecodeError):
            safe_json_parse(json_str)


class TestParseArgs:
    """Test the parse_args function with retry and concatenation support."""

    def test_valid_dict_passthrough(self):
        """Test that valid dict is passed through unchanged."""
        args = {"name": "test", "value": 42}
        result = parse_args(args)
        assert result == args

    def test_valid_json_string(self):
        """Test that valid JSON string is parsed correctly."""
        args = '{"name": "test", "value": 42}'
        result = parse_args(args)
        assert result == {"name": "test", "value": 42}

    def test_invalid_args_type_raises_error(self):
        """Test that invalid args type raises ValidationError."""
        with pytest.raises(ValidationError):
            parse_args(123)

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises ValidationError."""
        with pytest.raises(ValidationError):
            parse_args('{"invalid": json}')

    @patch("tunacode.cli.repl_components.command_parser.retry_json_parse")
    def test_retry_logic_used(self, mock_retry):
        """Test that retry logic is used for JSON parsing."""
        mock_retry.return_value = {"success": True}
        result = parse_args('{"test": "value"}')
        mock_retry.assert_called_once()
        assert result == {"success": True}

    @patch("tunacode.cli.repl_components.command_parser.retry_json_parse")
    @patch("tunacode.cli.repl_components.command_parser.safe_json_parse")
    def test_concatenated_json_recovery(self, mock_safe_parse, mock_retry):
        """Test that concatenated JSON recovery is attempted."""
        # Simulate retry failing with "Extra data" error
        mock_retry.side_effect = json.JSONDecodeError("Extra data", "", 10)
        mock_safe_parse.return_value = {"recovered": True}

        result = parse_args('{"first": 1}{"second": 2}')

        mock_safe_parse.assert_called_once_with(
            '{"first": 1}{"second": 2}', allow_concatenated=True
        )
        assert result == {"recovered": True}

    @patch("tunacode.cli.repl_components.command_parser.retry_json_parse")
    @patch("tunacode.cli.repl_components.command_parser.safe_json_parse")
    def test_concatenated_json_recovery_list_result(self, mock_safe_parse, mock_retry):
        """Test concatenated JSON recovery with list result."""
        mock_retry.side_effect = json.JSONDecodeError("Extra data", "", 10)
        mock_safe_parse.return_value = [{"first": 1}, {"second": 2}]

        result = parse_args('{"first": 1}{"second": 2}')

        # Should return first object when list is returned
        assert result == {"first": 1}


class TestErrorRecovery:
    """Test error recovery mechanisms."""

    @pytest.mark.asyncio
    async def test_attempt_tool_recovery_keyword_filtering(self):
        """Test that tool recovery is triggered by correct keywords."""
        state_manager = Mock()

        # Should trigger recovery
        json_error = Exception("Invalid JSON: extra data")
        with patch(
            "tunacode.cli.repl_components.error_recovery.attempt_json_args_recovery"
        ) as mock_json_recovery:
            mock_json_recovery.return_value = False
            state_manager.session.messages = []
            result = await attempt_tool_recovery(json_error, state_manager)
            mock_json_recovery.assert_called_once()

        # Should not trigger recovery
        other_error = Exception("Some other error")
        state_manager.session.messages = []
        result = await attempt_tool_recovery(other_error, state_manager)
        assert result is False

    @pytest.mark.asyncio
    async def test_attempt_json_args_recovery_success(self):
        """Test successful JSON args recovery."""
        # Setup mock state manager with malformed tool call
        state_manager = Mock()
        state_manager.session.messages = [Mock()]

        mock_part = Mock()
        mock_part.tool_name = "read_file"
        mock_part.args = '{"file": "a.py"}{"file": "b.py"}'  # Concatenated JSON

        state_manager.session.messages[-1].parts = [mock_part]

        # Mock the tool_handler
        with patch("tunacode.cli.repl_components.error_recovery.tool_handler") as mock_handler:
            mock_handler.return_value = None

            error = Exception("Invalid JSON: extra data")
            result = await attempt_json_args_recovery(error, state_manager)

            # Should have recovered and executed tool
            assert result is True
            mock_handler.assert_called_once()

            # Args should be fixed to first object
            assert mock_part.args == {"file": "a.py"}

    @pytest.mark.asyncio
    async def test_attempt_json_args_recovery_no_structured_calls(self):
        """Test JSON args recovery when no structured calls present."""
        state_manager = Mock()
        state_manager.session.messages = [Mock()]
        state_manager.session.messages[-1].parts = [Mock()]  # No tool_name/args

        error = Exception("Invalid JSON: extra data")
        result = await attempt_json_args_recovery(error, state_manager)

        assert result is False


class TestIntegration:
    """Integration tests for the complete JSON recovery system."""

    @pytest.mark.asyncio
    async def test_end_to_end_concatenated_json_recovery(self):
        """Test complete recovery flow from parse error to successful execution."""
        # This would be an integration test that tests the complete flow
        # from a concatenated JSON error through the recovery mechanism
        # to successful tool execution
        pass

    def test_system_prompt_examples_work(self):
        """Test that the examples in the system prompt work correctly."""
        # Test correct examples
        correct_single = '{"filepath": "main.py"}'
        result = parse_args(correct_single)
        assert result == {"filepath": "main.py"}

        # Test that incorrect concatenated format would be handled
        incorrect_concat = '{"filepath": "main.py"}{"filepath": "config.py"}'
        # This should work due to our recovery mechanism
        result = parse_args(incorrect_concat)
        assert result == {"filepath": "main.py"}  # First object
