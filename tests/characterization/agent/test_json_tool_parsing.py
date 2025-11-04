"""
Characterization tests for JSON tool call parsing functionality.
These tests capture the CURRENT behavior of parse_json_tool_calls() and related functions.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from tunacode.core.agents.agent_components import (
    extract_and_execute_tool_calls,
    parse_json_tool_calls,
)

pytestmark = pytest.mark.asyncio


class TestJsonToolParsing:
    """Golden-master tests for JSON tool parsing behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = Mock()
        self.state_manager.session = Mock()
        self.state_manager.session.messages = []
        self.state_manager.session.show_thoughts = False
        self.state_manager.session.tool_calls = []
        self.state_manager.session.files_in_context = set()

    async def test_parse_json_tool_calls_simple(self):
        """Capture behavior with simple JSON tool call."""
        # Arrange
        text = '{"tool": "read_file", "args": {"file_path": "/tmp/test.txt"}}'
        tool_callback = AsyncMock()

        # Act
        await parse_json_tool_calls(text, tool_callback, self.state_manager)

        # Assert - Golden master
        tool_callback.assert_called_once()
        call_args = tool_callback.call_args[0]
        mock_tool_call = call_args[0]

        assert mock_tool_call.tool_name == "read_file"
        assert mock_tool_call.args == {"file_path": "/tmp/test.txt"}
        assert mock_tool_call.tool_call_id.startswith("fallback_")

    async def test_parse_json_tool_calls_multiple(self):
        """Capture behavior with multiple JSON tool calls."""
        # Arrange
        text = """
        Some text before
        {"tool": "write_file", "args": {"file_path": "/tmp/out.txt", "content": "test"}}
        More text
        {"tool": "bash", "args": {"command": "ls -la"}}
        End text
        """
        tool_callback = AsyncMock()

        # Act
        await parse_json_tool_calls(text, tool_callback, self.state_manager)

        # Assert - Golden master
        assert tool_callback.call_count == 2

        # First call
        first_call = tool_callback.call_args_list[0][0][0]
        assert first_call.tool_name == "write_file"
        assert first_call.args == {"file_path": "/tmp/out.txt", "content": "test"}

        # Second call
        second_call = tool_callback.call_args_list[1][0][0]
        assert second_call.tool_name == "bash"
        assert second_call.args == {"command": "ls -la"}

    async def test_parse_json_tool_calls_nested_braces(self):
        """Capture behavior with nested braces in JSON."""
        # Arrange
        text = (
              '{"tool": "update_file", "args": {"file_path": "test.py", '
              '"pattern": "def func():", "replacement": "def func(arg: dict = {}):"}}'
          )
        tool_callback = AsyncMock()

        # Act
        await parse_json_tool_calls(text, tool_callback, self.state_manager)

        # Assert - Golden master
        tool_callback.assert_called_once()
        call_args = tool_callback.call_args[0][0]
        assert call_args.tool_name == "update_file"
        assert call_args.args["replacement"] == "def func(arg: dict = {}):"

    async def test_parse_json_tool_calls_invalid_json(self):
        """Capture behavior with invalid JSON (should be skipped)."""
        # Arrange
        text = '{"tool": "bash", "args": {broken json}}'
        tool_callback = AsyncMock()

        # Act
        await parse_json_tool_calls(text, tool_callback, self.state_manager)

        # Assert - Golden master
        tool_callback.assert_not_called()

    async def test_parse_json_tool_calls_no_callback(self):
        """Capture behavior when no callback provided."""
        # Arrange
        text = '{"tool": "read_file", "args": {"file_path": "/tmp/test.txt"}}'

        # Act
        await parse_json_tool_calls(text, None, self.state_manager)

        # Assert - Golden master
        # Should return without error
        # No way to verify internals without callback

    async def test_parse_json_tool_calls_with_thoughts_enabled(self):
        """Capture behavior with thoughts display enabled."""
        # Arrange
        self.state_manager.session.show_thoughts = True
        text = '{"tool": "list_dir", "args": {"directory": "/tmp"}}'
        tool_callback = AsyncMock()

        with patch("tunacode.ui.console.muted", new_callable=AsyncMock) as mock_muted:
            # Act
            await parse_json_tool_calls(text, tool_callback, self.state_manager)

            # Assert - Golden master
            tool_callback.assert_called_once()
            mock_muted.assert_called_with("FALLBACK: Executed list_dir via JSON parsing")

    async def test_parse_json_tool_calls_exception_handling(self):
        """Capture behavior when tool callback raises exception."""
        # Arrange
        self.state_manager.session.show_thoughts = True
        text = '{"tool": "grep", "args": {"pattern": "test"}}'
        tool_callback = AsyncMock(side_effect=Exception("Tool error"))

        with patch("tunacode.ui.console.error", new_callable=AsyncMock) as mock_error:
            # Act
            await parse_json_tool_calls(text, tool_callback, self.state_manager)

            # Assert - Golden master
            mock_error.assert_called_with("Error executing fallback tool grep: Tool error")

    async def test_extract_and_execute_tool_calls_inline_json(self):
        """Capture behavior extracting inline JSON tool calls."""
        # Arrange
        text = 'Here is a tool call: {"tool": "read_file", "args": {"file_path": "test.py"}}'
        tool_callback = AsyncMock()

        # Act
        await extract_and_execute_tool_calls(text, tool_callback, self.state_manager)

        # Assert - Golden master
        tool_callback.assert_called_once()

    async def test_extract_and_execute_tool_calls_code_blocks(self):
        """Capture behavior extracting tool calls from code blocks."""
        # Arrange
        text = """
        Here's a tool call in a code block:
        ```json
        {
          "tool": "write_file",
          "args": {
            "file_path": "output.txt",
            "content": "Hello, World!"
          }
        }
        ```
        """
        tool_callback = AsyncMock()

        # Act
        await extract_and_execute_tool_calls(text, tool_callback, self.state_manager)

        # Assert - Code block extraction was removed in refactoring
        # Only inline JSON is extracted
        assert tool_callback.call_count == 1  # Only inline JSON

        # Find the code block call
        for call in tool_callback.call_args_list:
            mock_call = call[0][0]
            if mock_call.tool_call_id.startswith("codeblock_"):
                assert mock_call.tool_name == "write_file"
                assert mock_call.args["file_path"] == "output.txt"
                assert mock_call.args["content"] == "Hello, World!"
                break

    async def test_extract_and_execute_tool_calls_mixed_formats(self):
        """Capture behavior with both inline and code block formats."""
        # Arrange
        text = """
        Inline: {"tool": "bash", "args": {"command": "pwd"}}

        Code block:
        ```json
        {"tool": "list_dir", "args": {"directory": "."}}
        ```
        """
        tool_callback = AsyncMock()

        # Act
        await extract_and_execute_tool_calls(text, tool_callback, self.state_manager)

        # Assert - Golden master
        # Code block extraction removed, duplicate inline JSON is only counted once
        assert tool_callback.call_count == 2  # Two unique inline JSON tools

        # Verify different tool types were called
        tool_names = [call[0][0].tool_name for call in tool_callback.call_args_list]
        assert "bash" in tool_names
        assert "list_dir" in tool_names

    async def test_extract_and_execute_tool_calls_invalid_code_block(self):
        """Capture behavior with invalid JSON in code block."""
        # Arrange
        self.state_manager.session.show_thoughts = True
        text = """
        ```json
        {"tool": "bash", invalid json here
        ```
        """
        tool_callback = AsyncMock()

        with patch("tunacode.ui.console.error", new_callable=AsyncMock) as mock_error:
            # Act
            await extract_and_execute_tool_calls(text, tool_callback, self.state_manager)

            # Assert - Golden master
            # The current implementation doesn't call error for invalid JSON in code blocks
            # It silently skips them. This captures the actual behavior.
            mock_error.assert_not_called()

            # Tool callback shouldn't be called for invalid JSON
            tool_callback.assert_not_called()
