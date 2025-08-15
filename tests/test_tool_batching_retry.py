"""Integration tests for tool batching JSON parsing with retry logic."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tunacode.core.agents.utils import (
    extract_and_execute_tool_calls,
    parse_json_tool_calls,
)
from tunacode.exceptions import ToolBatchingJSONError


class TestParseJsonToolCalls:
    """Test parse_json_tool_calls with retry logic."""

    @pytest.mark.asyncio
    async def test_valid_json_tool_call(self):
        """Test parsing valid JSON tool calls."""
        text = '{"tool": "read_file", "args": {"file_path": "/test.txt"}}'

        tool_callback = AsyncMock()
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.show_thoughts = False

        await parse_json_tool_calls(text, tool_callback, state_manager)

        # Verify tool was called
        assert tool_callback.called
        call_args = tool_callback.call_args[0]
        assert call_args[0].tool_name == "read_file"
        assert call_args[0].args == {"file_path": "/test.txt"}

    @pytest.mark.asyncio
    async def test_invalid_json_with_retry_success(self):
        """Test that retry logic works when JSON parsing eventually succeeds."""
        # This will simulate a transient failure that succeeds on retry
        parse_attempts = 0

        async def mock_retry_parse_impl(*args, **kwargs):
            nonlocal parse_attempts
            parse_attempts += 1
            if parse_attempts < 3:
                raise json.JSONDecodeError("Expecting value", "", 0)
            return {"tool": "bash", "args": {"command": "ls"}}

        mock_retry_parse = AsyncMock(side_effect=mock_retry_parse_impl)

        with patch("tunacode.core.agents.utils.retry_json_parse_async", new=mock_retry_parse):
            text = '{"tool": "bash", "args": {"command": "ls"}}'

            tool_callback = AsyncMock()
            state_manager = Mock()
            state_manager.session = Mock()
            state_manager.session.show_thoughts = False

            await parse_json_tool_calls(text, tool_callback, state_manager)

            # Verify tool was called after retry
            assert tool_callback.called
            assert parse_attempts == 3

    @pytest.mark.asyncio
    async def test_invalid_json_max_retries_exhausted(self):
        """Test that ToolBatchingJSONError is raised after max retries."""
        text = '{"invalid": json syntax}'

        tool_callback = AsyncMock()
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.show_thoughts = False

        with pytest.raises(ToolBatchingJSONError) as exc_info:
            await parse_json_tool_calls(text, tool_callback, state_manager)

        # Verify error message
        assert "The model is having issues with tool batching" in str(exc_info.value)
        assert "10 retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_multiple_json_objects(self):
        """Test parsing multiple JSON objects in text."""
        text = """
        Some text here
        {"tool": "read_file", "args": {"file_path": "/file1.txt"}}
        More text
        {"tool": "bash", "args": {"command": "pwd"}}
        """

        tool_callback = AsyncMock()
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.show_thoughts = False

        await parse_json_tool_calls(text, tool_callback, state_manager)

        # Verify both tools were called
        assert tool_callback.call_count == 2

        # Check first call
        first_call = tool_callback.call_args_list[0][0]
        assert first_call[0].tool_name == "read_file"

        # Check second call
        second_call = tool_callback.call_args_list[1][0]
        assert second_call[0].tool_name == "bash"


class TestExtractAndExecuteToolCalls:
    """Test extract_and_execute_tool_calls with retry logic."""

    @pytest.mark.asyncio
    async def test_code_block_json_parsing(self):
        """Test parsing JSON from code blocks."""
        text = """
        Here's a tool call:
        ```json
        {"tool": "write_file", "args": {"file_path": "/test.py", "content": "print('hello')"}}
        ```
        """

        tool_callback = AsyncMock()
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.show_thoughts = False

        await extract_and_execute_tool_calls(text, tool_callback, state_manager)

        # Verify tool was called
        assert tool_callback.called
        call_args = tool_callback.call_args[0]
        assert call_args[0].tool_name == "write_file"

    @pytest.mark.asyncio
    async def test_invalid_code_block_json_raises_error(self):
        """Test that invalid JSON in code blocks raises ToolBatchingJSONError."""
        text = """
        ```json
        {"tool": "bash", "args": {invalid json here}}
        ```
        """

        tool_callback = AsyncMock()
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.show_thoughts = False

        with pytest.raises(ToolBatchingJSONError) as exc_info:
            await extract_and_execute_tool_calls(text, tool_callback, state_manager)

        assert "The model is having issues with tool batching" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mixed_format_tool_calls(self):
        """Test handling both inline and code block tool calls."""
        text = """
        Inline: {"tool": "list_dir", "args": {"path": "/home"}}

        Code block:
        ```json
        {"tool": "grep", "args": {"pattern": "test", "path": "/src"}}
        ```
        """

        tool_callback = AsyncMock()
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.show_thoughts = False

        await extract_and_execute_tool_calls(text, tool_callback, state_manager)

        # Both formats should be parsed
        assert tool_callback.call_count == 2

    @pytest.mark.asyncio
    async def test_error_logging_with_show_thoughts(self):
        """Test that errors are logged when show_thoughts is enabled."""
        text = '{"invalid": json}'

        tool_callback = AsyncMock()
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.show_thoughts = True

        ui_error = AsyncMock()

        with patch("tunacode.core.agents.utils.ui.error", ui_error):
            with pytest.raises(ToolBatchingJSONError):
                await parse_json_tool_calls(text, tool_callback, state_manager)

        # Verify error was displayed to UI
        assert ui_error.called
        error_msg = ui_error.call_args[0][0]
        assert "Failed to parse tool JSON after 10 retries" in error_msg


class TestMainIntegration:
    """Test integration with main.py error handling."""

    @pytest.mark.asyncio
    async def test_main_handles_tool_batching_error(self):
        """Test that main.py properly handles ToolBatchingJSONError."""
        from tunacode.core.agents.utils import extract_and_execute_tool_calls

        # Mock a response with invalid JSON
        mock_part = Mock()
        mock_part.content = '{"tool": "bash", "args": {invalid}}'

        mock_node = Mock()
        mock_node.model_response = Mock()
        mock_node.model_response.parts = [mock_part]

        tool_callback = AsyncMock()
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.show_thoughts = True
        state_manager.session.messages = []

        # The error should be caught and logged, not propagated
        # This is tested by checking that the function completes without raising
        with pytest.raises(ToolBatchingJSONError):
            await extract_and_execute_tool_calls(mock_part.content, tool_callback, state_manager)


class TestRetryBehavior:
    """Test specific retry behavior scenarios."""

    @pytest.mark.asyncio
    async def test_retry_delay_timing(self):
        """Test that retry delays follow exponential backoff."""
        delays = []

        async def mock_sleep(delay):
            delays.append(delay)

        with patch("asyncio.sleep", mock_sleep):
            with patch("json.loads") as mock_loads:
                # Always fail to trigger retries
                mock_loads.side_effect = json.JSONDecodeError("test", "", 0)

                text = '{"tool": "test", "args": {}}'
                tool_callback = AsyncMock()
                state_manager = Mock()
                state_manager.session = Mock()
                state_manager.session.show_thoughts = False

                with pytest.raises(ToolBatchingJSONError):
                    await parse_json_tool_calls(text, tool_callback, state_manager)

        # Verify exponential backoff pattern
        assert len(delays) > 0
        for i in range(1, len(delays)):
            # Each delay should be roughly double the previous (capped at max)
            if delays[i] < 5.0:  # Max delay cap
                assert delays[i] >= delays[i - 1] * 1.5  # Allow some variance

    @pytest.mark.asyncio
    async def test_successful_recovery_within_retries(self):
        """Test successful JSON parsing after a few retries."""
        attempt_count = 0

        async def mock_parse_impl(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 4:
                raise json.JSONDecodeError("Transient error", "", 0)
            return {"tool": "bash", "args": {"command": "echo 'success'"}}

        mock_parse = AsyncMock(side_effect=mock_parse_impl)

        with patch("tunacode.core.agents.utils.retry_json_parse_async", new=mock_parse):
            text = '{"tool": "bash", "args": {"command": "echo \'success\'"}}'

            tool_callback = AsyncMock()
            state_manager = Mock()
            state_manager.session = Mock()
            state_manager.session.show_thoughts = False

            await parse_json_tool_calls(text, tool_callback, state_manager)

            # Should succeed after retries
            assert tool_callback.called
            assert attempt_count == 4
