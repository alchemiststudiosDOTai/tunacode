"""
Characterization tests for repl.py refactoring.

These tests capture the current behavior of the REPL (Read-Eval-Print Loop)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tunacode.cli.repl import (
    MSG_AGENT_BUSY,
    MSG_HIT_ABORT_KEY,
    MSG_OPERATION_ABORTED,
    MSG_SESSION_ENDED,
    _handle_command,
    process_request,
    repl,
)
from tunacode.cli.repl_components import attempt_tool_recovery as _attempt_tool_recovery
from tunacode.cli.repl_components import display_agent_output as _display_agent_output
from tunacode.cli.repl_components import parse_args as _parse_args
from tunacode.cli.repl_components import tool_handler as _tool_handler
from tunacode.cli.repl_components.error_recovery import MSG_JSON_RECOVERY
from tunacode.exceptions import UserAbortError, ValidationError
from tunacode.types import StateManager


class TestReplCharacterization:
    """Test suite capturing current REPL behavior."""

    @pytest.fixture
    def mock_state_manager(self):
        """Create a mock state manager with required attributes."""
        state_manager = MagicMock(spec=StateManager)

        # Setup session attributes
        state_manager.session = MagicMock()
        state_manager.session.current_iteration = 0
        state_manager.session.enable_streaming = False
        state_manager.session.interrupt_count = 0
        state_manager.session.operation_cancelled = False
        state_manager.session.agent_busy = False
        state_manager.session.context_window = 100000
        state_manager.session.session_complete = False
        state_manager.session.error_count = 0
        state_manager.session.total_cost = 0.0
        state_manager.session.show_thoughts = False
        state_manager.session.files_in_context = set()
        state_manager.session.user_config = {"settings": {}}

        # Setup tool handler
        state_manager.tool_handler = None

        # Setup permission tracking
        state_manager.get_permission = MagicMock(return_value=True)
        state_manager.get_shell_permission = MagicMock(return_value=True)
        state_manager.set_tool_handler = MagicMock()

        # Mock for messages
        state_manager.session.messages = []

        # Add is_plan_mode mock for plan mode UI
        state_manager.is_plan_mode = MagicMock(return_value=False)

        return state_manager

    def test_parse_args_with_string(self):
        """Test parsing JSON string arguments."""
        args_str = '{"file_path": "test.py", "content": "print(\'hello\')"}'
        result = _parse_args(args_str)

        assert result == {"file_path": "test.py", "content": "print('hello')"}

    def test_parse_args_with_dict(self):
        """Test parsing dictionary arguments."""
        args_dict = {"file_path": "test.py", "content": "print('hello')"}
        result = _parse_args(args_dict)

        assert result == args_dict

    def test_parse_args_invalid_json(self):
        """Test parsing invalid JSON raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _parse_args("{invalid json}")

        assert "Invalid JSON" in str(exc_info.value)

    def test_parse_args_invalid_type(self):
        """Test parsing invalid type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _parse_args(12345)

        assert "Invalid args type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tool_handler_cancelled_operation(self, mock_state_manager):
        """Test tool handler when operation is cancelled."""
        mock_state_manager.session.operation_cancelled = True

        with pytest.raises(asyncio.CancelledError):
            await _tool_handler(MagicMock(), mock_state_manager)

    @pytest.mark.asyncio
    async def test_tool_handler_creates_handler(self, mock_state_manager):
        """Test tool handler creates handler when none exists."""
        mock_part = MagicMock()
        mock_part.tool_name = "read_file"
        mock_part.args = {"file_path": "test.py"}

        with patch("tunacode.cli.repl_components.tool_executor.ToolHandler") as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler.should_confirm.return_value = False  # Don't show confirmation
            mock_handler.execute_tool = AsyncMock(return_value="file contents")
            mock_handler.is_tool_blocked_in_plan_mode = MagicMock(return_value=False)
            mock_handler_class.return_value = mock_handler

            # Mock the state_manager to have is_streaming_active and spinner
            mock_state_manager.session.is_streaming_active = False
            mock_state_manager.session.spinner = None

            await _tool_handler(mock_part, mock_state_manager)

            # The test is about setting tool_handler on state_manager
            mock_state_manager.set_tool_handler.assert_called_once_with(mock_handler)

    @pytest.mark.asyncio
    async def test_handle_command_shell_command(self, mock_state_manager):
        """Test handling shell commands starting with !."""
        command = "!ls -la"

        # Shell commands return string or None, not CommandResult
        result = await _handle_command(command, mock_state_manager)

        # Shell commands don't return CommandResult, they print directly
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_command_registry_command(self, mock_state_manager):
        """Test handling registered commands."""
        command = "/help"

        # Commands may return None, string (restart), or other values
        with patch("tunacode.cli.repl._command_registry") as mock_registry:
            mock_registry.execute = AsyncMock(return_value=None)

            result = await _handle_command(command, mock_state_manager)

            # Most commands return None
            assert result is None

    @pytest.mark.asyncio
    async def test_handle_command_invalid(self, mock_state_manager):
        """Test handling invalid commands."""
        command = "/invalid_command"

        with patch("tunacode.cli.repl._command_registry") as mock_registry:
            mock_registry.execute = AsyncMock(side_effect=ValidationError("Unknown command"))

            with patch("tunacode.cli.repl.ui.error") as mock_error:
                result = await _handle_command(command, mock_state_manager)

                # Unknown commands show error and return None
                mock_error.assert_called()
                assert result is None

    @pytest.mark.asyncio
    async def test_process_request_basic(self, mock_state_manager):
        """Test basic request processing."""
        text = "Write a hello world program"

        # Disable streaming for this test to ensure display_agent_output is called
        mock_state_manager.session.user_config = {"settings": {"enable_streaming": False}}
        # Mock show_thoughts to avoid additional output
        mock_state_manager.session.show_thoughts = False
        # Mock files_in_context to be empty
        mock_state_manager.session.files_in_context = set()

        with patch("tunacode.cli.repl.agent.process_request") as mock_agent_process:
            # Create a mock agent run
            mock_run = MagicMock()
            mock_run.result = MagicMock()
            mock_run.result.output = "Here's a hello world program:\n\nprint('Hello, World!')"

            mock_agent_process.return_value = mock_run

            with patch("tunacode.cli.repl.display_agent_output") as mock_display:
                mock_display.return_value = None

                await process_request(text, mock_state_manager)

                mock_agent_process.assert_called_once()
                mock_display.assert_called_once_with(mock_run, False, mock_state_manager)

    @pytest.mark.asyncio
    async def test_process_request_with_error(self, mock_state_manager):
        """Test request processing with error handling."""
        text = "Cause an error"

        with patch("tunacode.cli.repl.agent.process_request") as mock_agent_process:
            mock_agent_process.side_effect = Exception("Test error")

            with patch("tunacode.cli.repl.ui.error") as mock_error:
                await process_request(text, mock_state_manager)

                mock_error.assert_called()
                # Error handling happens but error_count might not be directly incremented
                mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_process_request_user_abort(self, mock_state_manager):
        """Test request processing with user abort."""
        text = "Do something"

        with patch("tunacode.cli.repl.agent.process_request") as mock_agent_process:
            mock_agent_process.side_effect = UserAbortError("User cancelled")

            with patch("tunacode.cli.repl.ui.muted") as mock_muted:
                await process_request(text, mock_state_manager)

                mock_muted.assert_called_with(MSG_OPERATION_ABORTED)

    @pytest.mark.asyncio
    async def test_repl_basic_interaction(self, mock_state_manager):
        """Test basic REPL interaction."""
        # Ensure _startup_shown is not set to trigger the startup message
        if hasattr(mock_state_manager.session, "_startup_shown"):
            delattr(mock_state_manager.session, "_startup_shown")

        # Mock agent instance
        mock_instance = MagicMock()
        # Create a proper async context manager mock
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=None)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_instance.run_mcp_servers.return_value = mock_context

        with patch("tunacode.cli.repl.agent.get_or_create_agent", return_value=mock_instance):
            with patch("tunacode.cli.repl.ui.multiline_input") as mock_input:
                # Mock prompt returning exit immediately
                mock_input.side_effect = ["exit"]

                with patch("tunacode.cli.repl.ui.muted"):
                    with patch("tunacode.cli.repl.ui.success") as mock_success:
                        with patch("tunacode.cli.repl.ui.line"):
                            await repl(mock_state_manager)

                            # Should show startup info
                            mock_success.assert_called_with("Ready to assist")

    @pytest.mark.asyncio
    async def test_repl_keyboard_interrupt_handling(self, mock_state_manager):
        """Test REPL handles keyboard interrupts properly."""
        mock_instance = MagicMock()
        # Create a proper async context manager mock
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=None)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_instance.run_mcp_servers.return_value = mock_context

        with patch("tunacode.cli.repl.agent.get_or_create_agent", return_value=mock_instance):
            with patch("tunacode.cli.repl.ui.multiline_input") as mock_input:
                # First raises UserAbortError, second returns exit
                mock_input.side_effect = [UserAbortError(), "exit"]

                with patch("tunacode.cli.repl.ui.warning") as mock_warning:
                    await repl(mock_state_manager)

                    # Should show Ctrl+C warning
                    mock_warning.assert_called_with(MSG_HIT_ABORT_KEY)

    @pytest.mark.asyncio
    async def test_repl_agent_busy_state(self, mock_state_manager):
        """Test REPL behavior when agent is busy."""
        # Create a mock task that is not done
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_state_manager.session.current_task = mock_task

        mock_instance = MagicMock()
        # Create a proper async context manager mock
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=None)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_instance.run_mcp_servers.return_value = mock_context

        with patch("tunacode.cli.repl.agent.get_or_create_agent", return_value=mock_instance):
            with patch("tunacode.cli.repl.ui.multiline_input") as mock_input:
                # First input when busy, then exit
                mock_input.side_effect = ["test command", "exit"]

                with patch("tunacode.cli.repl.ui.muted") as mock_muted:
                    with patch("tunacode.cli.repl.get_app") as mock_app:
                        # Reset task state for second iteration
                        def reset_task():
                            mock_state_manager.session.current_task = None

                        mock_app.return_value.create_background_task.side_effect = reset_task

                        await repl(mock_state_manager)

                        # Should show agent busy message
                        assert any(
                            MSG_AGENT_BUSY in str(call) for call in mock_muted.call_args_list
                        )

    @pytest.mark.asyncio
    async def test_display_agent_output_streaming(self):
        """Test displaying agent output with streaming enabled."""
        # When streaming is enabled, the function returns immediately
        mock_run = MagicMock()
        mock_run.result = MagicMock()
        mock_run.result.output = "Test output"

        await _display_agent_output(mock_run, enable_streaming=True)

        # Nothing should be called when streaming is enabled
        # The function returns immediately

    @pytest.mark.asyncio
    async def test_display_agent_output_non_streaming(self):
        """Test displaying agent output without streaming."""
        mock_run = MagicMock()
        mock_run.result = MagicMock()
        mock_run.result.output = "Test output"

        # No response state for non-streaming
        mock_run.response_state = None

        with patch("tunacode.cli.repl.ui.agent") as mock_agent:
            with patch("tunacode.cli.repl.ui.muted") as mock_muted:
                await _display_agent_output(mock_run, enable_streaming=False)

                # Should use agent output
                mock_agent.assert_called_with("Test output")
                # Should not show completion message for normal output
                mock_muted.assert_not_called()

    @pytest.mark.asyncio
    async def test_attempt_tool_recovery(self, mock_state_manager):
        """Test tool recovery mechanism for JSON parsing errors."""
        # Mock an exception with tool call JSON in message
        error_msg = 'Failed to parse: {"tool": "read_file", "args": {"file_path": "test.py"}}'
        exception = Exception(error_msg)

        # Add a message with parts to the session
        mock_msg = MagicMock()
        mock_msg.parts = [MagicMock(content=error_msg)]
        mock_state_manager.session.messages = [mock_msg]

        with patch("tunacode.cli.repl.agent.extract_and_execute_tool_calls") as mock_extract:
            mock_extract.return_value = 1  # Indicates 1 tool was recovered

            with patch("tunacode.cli.repl.ui.warning") as mock_warning:
                result = await _attempt_tool_recovery(exception, mock_state_manager)

                assert result is True
                # Check that recovery message is shown
                assert any(MSG_JSON_RECOVERY in str(call) for call in mock_warning.call_args_list)

    def test_repl_imports(self):
        """Test that all required imports are available."""
        # This test ensures critical imports exist
        from tunacode.cli.repl import DEFAULT_SHELL, SHELL_ENV_VAR

        # Check constants are defined
        assert MSG_OPERATION_ABORTED == "Operation aborted."
        assert MSG_SESSION_ENDED == "Session ended. Happy coding!"
        assert SHELL_ENV_VAR == "SHELL"
        assert DEFAULT_SHELL == "bash"
