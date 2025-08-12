"""Tests for command parser retry functionality."""

import json
from unittest.mock import patch

import pytest

from tunacode.cli.repl_components.command_parser import parse_args
from tunacode.exceptions import ValidationError


class TestCommandParserRetry:
    """Test retry functionality in command parser."""

    @patch("tunacode.cli.repl_components.command_parser.retry_json_parse")
    def test_retry_called_with_correct_parameters(self, mock_retry):
        """Test that retry is called with correct parameters."""
        mock_retry.return_value = {"test": "success"}

        result = parse_args('{"test": "value"}')

        mock_retry.assert_called_once()
        call_args = mock_retry.call_args
        assert call_args[0][0] == '{"test": "value"}'  # json_string
        assert "max_retries" in call_args[1]
        assert "base_delay" in call_args[1]
        assert "max_delay" in call_args[1]
        assert result == {"test": "success"}

    @patch("tunacode.cli.repl_components.command_parser.retry_json_parse")
    def test_retry_failure_falls_back_to_concatenation_check(self, mock_retry):
        """Test that retry failure with Extra data triggers concatenation handling."""
        mock_retry.side_effect = json.JSONDecodeError(
            "Expecting ',' delimiter: line 1 column 15 (char 14): Extra data", "", 14
        )

        with patch("tunacode.cli.repl_components.command_parser.safe_json_parse") as mock_safe:
            mock_safe.return_value = {"recovered": True}

            result = parse_args('{"a": 1}{"b": 2}')

            mock_safe.assert_called_once_with('{"a": 1}{"b": 2}', allow_concatenated=True)
            assert result == {"recovered": True}

    @patch("tunacode.cli.repl_components.command_parser.retry_json_parse")
    def test_retry_failure_without_extra_data_raises_validation_error(self, mock_retry):
        """Test that retry failure without Extra data raises ValidationError."""
        mock_retry.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with pytest.raises(ValidationError) as exc_info:
            parse_args('{"invalid": }')

        assert "Invalid JSON" in str(exc_info.value)

    @patch("tunacode.cli.repl_components.command_parser.retry_json_parse")
    def test_concatenation_recovery_with_list_result(self, mock_retry):
        """Test concatenation recovery when safe_json_parse returns a list."""
        mock_retry.side_effect = json.JSONDecodeError("Extra data", "", 10)

        with patch("tunacode.cli.repl_components.command_parser.safe_json_parse") as mock_safe:
            mock_safe.return_value = [{"first": 1}, {"second": 2}]

            result = parse_args('{"first": 1}{"second": 2}')

            # Should return first object from list
            assert result == {"first": 1}

    @patch("tunacode.cli.repl_components.command_parser.retry_json_parse")
    def test_concatenation_recovery_failure_raises_validation_error(self, mock_retry):
        """Test that failed concatenation recovery raises ValidationError."""
        mock_retry.side_effect = json.JSONDecodeError("Extra data", "", 10)

        with patch("tunacode.cli.repl_components.command_parser.safe_json_parse") as mock_safe:
            mock_safe.side_effect = Exception("Safe parsing failed")

            with pytest.raises(ValidationError) as exc_info:
                parse_args('{"a": 1}invalid{"b": 2}')

            assert "Invalid JSON" in str(exc_info.value)

    def test_dict_passthrough_no_retry(self):
        """Test that dict args don't trigger retry logic."""
        args = {"direct": "dict"}

        with patch("tunacode.cli.repl_components.command_parser.retry_json_parse") as mock_retry:
            result = parse_args(args)

            mock_retry.assert_not_called()
            assert result == args

    def test_invalid_type_raises_validation_error(self):
        """Test that invalid argument types raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            parse_args(123)

        assert "Invalid args type" in str(exc_info.value)

    def test_none_raises_validation_error(self):
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError):
            parse_args(None)

    @patch("tunacode.cli.repl_components.command_parser.retry_json_parse")
    def test_empty_string_raises_validation_error(self, mock_retry):
        """Test that empty string raises ValidationError."""
        mock_retry.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with pytest.raises(ValidationError):
            parse_args("")

    @patch("tunacode.cli.repl_components.command_parser.retry_json_parse")
    def test_whitespace_only_string_raises_validation_error(self, mock_retry):
        """Test that whitespace-only string raises ValidationError."""
        mock_retry.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with pytest.raises(ValidationError):
            parse_args("   ")


class TestRealWorldScenarios:
    """Test real-world scenarios that might occur."""

    def test_common_concatenation_pattern(self):
        """Test the specific pattern mentioned in the incident report."""
        # This is the exact pattern from the incident report
        concatenated_args = (
            '{"filepath": "main.py"}{"filepath": "__init__.py"}{"filepath": "cli/main.py"}'
        )

        # Should not raise an exception due to our recovery mechanism
        result = parse_args(concatenated_args)

        # Should return the first object
        assert result == {"filepath": "main.py"}

    def test_file_operations_concatenation(self):
        """Test concatenation patterns common in file operations."""
        patterns = [
            '{"file": "a.py"}{"file": "b.py"}',
            '{"path": "/src/main.py"}{"path": "/src/utils.py"}',
            '{"filename": "test1.txt"}{"filename": "test2.txt"}{"filename": "test3.txt"}',
        ]

        for pattern in patterns:
            result = parse_args(pattern)
            # Should always return the first object
            assert isinstance(result, dict)
            assert len(result) > 0

    def test_complex_nested_concatenation(self):
        """Test concatenation with complex nested objects."""
        complex_pattern = """{"tool": "read_file", "args": {"file": "main.py", "options": {"encoding": "utf-8"}}}{"tool": "read_file", "args": {"file": "config.py"}}"""

        result = parse_args(complex_pattern)

        expected_first = {
            "tool": "read_file",
            "args": {"file": "main.py", "options": {"encoding": "utf-8"}},
        }
        assert result == expected_first

    def test_mixed_valid_invalid_concatenation(self):
        """Test concatenation with mix of valid and invalid JSON."""
        mixed_pattern = '{"valid": true}{invalid json}{"also_valid": false}'

        # Should recover the first valid object
        result = parse_args(mixed_pattern)
        assert result == {"valid": True}

    @patch("tunacode.cli.repl_components.command_parser.logger")
    def test_logging_on_concatenation_recovery(self, mock_logger):
        """Test that appropriate logging occurs during recovery."""
        concatenated_args = '{"first": 1}{"second": 2}'

        result = parse_args(concatenated_args)

        # Should have logged the detection of concatenated objects
        mock_logger.warning.assert_called()
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "concatenated JSON objects" in str(call)
        ]
        assert len(warning_calls) > 0

        assert result == {"first": 1}
