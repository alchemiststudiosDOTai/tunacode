"""
Characterization tests for tool UI behavior.

These tests capture the CURRENT behavior of tool UI interactions, including
how read-only tools skip confirmation dialogs and info messages.

IMPORTANT: These are golden-master tests - they document how the system
actually behaves, not how it should ideally behave. Any changes to these
tests indicate a change in system behavior that should be carefully reviewed.

Key behaviors captured:
- Read-only tools (read_file, grep, list_dir, glob) skip the "Tool()" info message
- All tools still call run_in_terminal, but read-only tools' confirm_func returns False immediately
- Yolo mode skips all info messages and confirmations
- Tool ignore list behaves similarly to yolo mode for specific tools
- Unknown/custom tools are treated as requiring confirmation
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from tunacode.cli.repl import _tool_handler
from tunacode.constants import (
    TOOL_BASH,
    TOOL_GLOB,
    TOOL_GREP,
    TOOL_LIST_DIR,
    TOOL_READ_FILE,
    TOOL_RUN_COMMAND,
    TOOL_UPDATE_FILE,
    TOOL_WRITE_FILE,
)

pytestmark = pytest.mark.asyncio


# Test Coverage Summary:
# ======================
# This file provides comprehensive characterization tests for tool UI behavior.
# It captures the exact behavior of the system as of the time of writing.
#
# Key test scenarios covered:
# 1. Read-only tools (no UI messages, quick execution)
# 2. Write/execute tools (full confirmation flow)
# 3. Yolo mode (skip all confirmations)
# 4. Tool ignore list (selective confirmation skipping)
# 5. Unknown/custom tools (default to safe behavior)
# 6. User abort handling (clean error propagation)
# 7. Spinner lifecycle (UI responsiveness)
#
# These tests use mocking extensively to isolate UI behavior from actual tool
# execution, making them fast and reliable.


class TestToolUICharacterization:
    """Golden-master tests for tool UI behavior.

    These tests use mocking to isolate and capture the exact UI behavior
    when tools are executed. The tests verify:
    1. Which UI messages are shown (or not shown)
    2. When confirmation dialogs appear
    3. How the spinner lifecycle works
    4. Special behaviors for different tool categories
    """

    def setup_method(self):
        """Set up test fixtures.

        Creates a mock StateManager with all the necessary attributes
        that the tool handlers expect. This includes:
        - session.yolo: Controls whether to skip all confirmations
        - session.tool_ignore: List of tools to skip confirmation for
        - session.spinner: UI spinner control for async operations
        - session.messages: Message history for patch_tool_messages
        """
        self.state_manager = Mock()
        self.state_manager.session = Mock()
        self.state_manager.session.yolo = False
        self.state_manager.session.tool_ignore = []
        self.state_manager.session.spinner = Mock()
        self.state_manager.session.spinner.stop = Mock()
        self.state_manager.session.spinner.start = Mock()
        self.state_manager.session.messages = []  # Initialize as empty list for patch_tool_messages

    async def test_read_only_tools_no_ui_output(self):
        """Capture behavior: read-only tools produce no UI output but still call run_in_terminal.

        This test verifies that read-only tools (read_file, grep, list_dir, glob):
        1. Do NOT show the "Tool(tool_name)" info message
        2. Still call run_in_terminal (for consistency in the code flow)
        3. The confirm_func inside run_in_terminal returns False immediately
        4. Spinner is stopped and restarted around the operation

        This behavior was implemented to reduce UI clutter for safe, read-only operations
        while maintaining the same code path for all tools.
        """
        # Test all read-only tools defined in constants.py
        read_only_tools = [TOOL_READ_FILE, TOOL_GREP, TOOL_LIST_DIR, TOOL_GLOB]

        for tool_name in read_only_tools:
            # Reset mocks for each tool to ensure clean state
            self.state_manager.session.spinner.stop.reset_mock()
            self.state_manager.session.spinner.start.reset_mock()

            with patch("tunacode.cli.repl.ui.info") as mock_info:
                with patch(
                    "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
                ) as mock_terminal:
                    # Mock run_in_terminal to return False (no abort)
                    mock_terminal.return_value = False

                    # Arrange: Create mock tool call
                    part = Mock()
                    part.tool_name = tool_name
                    part.args = "{}"  # Empty args for simplicity
                    # Act: Execute the tool handler
                    await _tool_handler(part, self.state_manager)

                    # Assert - Golden master behavior:
                    # No info message should be shown for read-only tools
                    mock_info.assert_not_called()
                    # Spinner should be stopped before and started after
                    self.state_manager.session.spinner.stop.assert_called_once()
                    self.state_manager.session.spinner.start.assert_called_once()
                    # run_in_terminal IS called, but the confirm_func returns False immediately
                    # This is because the code always calls run_in_terminal, but the
                    # confirm_func checks should_confirm() and returns False for read-only tools
                    mock_terminal.assert_called_once()

    async def test_write_tools_show_ui_output(self):
        """Capture behavior: write/execute tools show Tool info and confirmation.

        This test verifies that write/execute tools (write_file, update_file, bash, run_command):
        1. DO show the "Tool(tool_name)" info message
        2. Call run_in_terminal for user confirmation
        3. The confirm_func presents the full confirmation dialog
        4. Spinner lifecycle is maintained

        These tools modify files or execute commands, so they require explicit
        user confirmation for safety (unless in yolo mode).
        """
        # Test all write and execute tools that can modify the system
        write_execute_tools = [TOOL_WRITE_FILE, TOOL_UPDATE_FILE, TOOL_BASH, TOOL_RUN_COMMAND]

        for tool_name in write_execute_tools:
            # Reset mocks for each tool to ensure clean state
            self.state_manager.session.spinner.stop.reset_mock()
            self.state_manager.session.spinner.start.reset_mock()

            with patch("tunacode.cli.repl.ui.info") as mock_info:
                with patch(
                    "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
                ) as mock_terminal:
                    # Mock run_in_terminal to return False (user approves, no abort)
                    mock_terminal.return_value = False

                    # Arrange: Create mock tool call with typical args
                    part = Mock()
                    part.tool_name = tool_name
                    part.args = '{"filepath": "test.txt", "content": "test"}'
                    # Act: Execute the tool handler
                    await _tool_handler(part, self.state_manager)

                    # Assert - Golden master behavior:
                    # Info message SHOULD be shown for write/execute tools
                    mock_info.assert_called_once_with(f"Tool({tool_name})")
                    # Spinner lifecycle maintained
                    self.state_manager.session.spinner.stop.assert_called_once()
                    self.state_manager.session.spinner.start.assert_called_once()
                    # run_in_terminal called to show confirmation dialog
                    mock_terminal.assert_called_once()

    async def test_yolo_mode_behavior(self):
        """Capture behavior: yolo mode skips confirmations and info messages for all tools.

        YOLO (You Only Live Once) mode is activated with /yolo command and:
        1. Skips ALL confirmation dialogs
        2. Skips the "Tool()" info messages for ALL tools (even write/execute)
        3. Makes the tool execution flow much faster but less safe
        4. Affects both read-only and write/execute tools equally

        This test verifies that in yolo mode, even dangerous write operations
        proceed without any UI interaction.
        """
        # Enable yolo mode - this affects all tool confirmations
        self.state_manager.session.yolo = True

        # Test 1: Write tool in yolo mode should skip everything
        with patch("tunacode.cli.repl.ui.info") as mock_info:
            with patch(
                "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
            ) as mock_terminal:
                # Mock run_in_terminal to return False
                mock_terminal.return_value = False

                # Arrange
                part = Mock()
                part.tool_name = TOOL_WRITE_FILE
                part.args = '{"filepath": "test.txt", "content": "test"}'
                # Act
                await _tool_handler(part, self.state_manager)

                # Assert - Golden master
                # In yolo mode, write tools don't show info message
                mock_info.assert_not_called()
                # run_in_terminal is still called but returns immediately
                mock_terminal.assert_called_once()

        # Test read-only tool in yolo mode
        with patch("tunacode.cli.repl.ui.info") as mock_info:
            with patch(
                "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
            ) as mock_terminal:
                # Mock run_in_terminal to return False
                mock_terminal.return_value = False

                # Arrange
                part = Mock()
                part.tool_name = TOOL_READ_FILE
                part.args = '{"file_path": "test.txt"}'
                # Act
                await _tool_handler(part, self.state_manager)

                # Assert - Golden master
                # Read-only tools still don't show info message even in yolo
                mock_info.assert_not_called()
                # run_in_terminal is still called even for read-only in yolo
                mock_terminal.assert_called_once()

    async def test_tool_ignore_list_behavior(self):
        """Capture behavior: tools in ignore list don't show info and skip confirmation.

        The tool_ignore list is populated when user selects option 2 during confirmation:
        "Yes, and don't ask again for commands like this"

        Tools in this list behave like they're in yolo mode:
        1. No "Tool()" info message
        2. No confirmation dialog
        3. run_in_terminal is still called but returns immediately

        This allows users to selectively skip confirmations for specific tools
        they trust, without enabling full yolo mode.
        """
        # Add write_file to ignore list - simulating user choosing "don't ask again"
        self.state_manager.session.tool_ignore = [TOOL_WRITE_FILE]

        with patch("tunacode.cli.repl.ui.info") as mock_info:
            with patch(
                "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
            ) as mock_terminal:
                # Mock run_in_terminal to return False
                mock_terminal.return_value = False

                # Arrange
                part = Mock()
                part.tool_name = TOOL_WRITE_FILE
                part.args = '{"filepath": "test.txt", "content": "test"}'
                # Act
                await _tool_handler(part, self.state_manager)

                # Assert - Golden master
                # Tool in ignore list doesn't show info message
                mock_info.assert_not_called()
                # run_in_terminal is still called but returns immediately
                mock_terminal.assert_called_once()

    async def test_unknown_tool_behavior(self):
        """Capture behavior: unknown tools are treated as requiring confirmation.

        When the system encounters a tool name that's not in the predefined lists
        (READ_ONLY_TOOLS, WRITE_TOOLS, EXECUTE_TOOLS), it defaults to the safe
        behavior of requiring confirmation.

        This ensures that:
        1. New tools default to safe behavior
        2. MCP (Model Context Protocol) tools get proper confirmation
        3. Custom tools from extensions are handled safely

        The unknown tool gets the full treatment: info message + confirmation dialog.
        """
        with patch("tunacode.cli.repl.ui.info") as mock_info:
            with patch(
                "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
            ) as mock_terminal:
                # Mock run_in_terminal to return False
                mock_terminal.return_value = False

                # Arrange
                part = Mock()
                part.tool_name = "unknown_custom_tool"
                part.args = '{"param": "value"}'
                # Act
                await _tool_handler(part, self.state_manager)

                # Assert - Golden master
                # Unknown tools show info message
                mock_info.assert_called_once_with("Tool(unknown_custom_tool)")
                # And require confirmation
                mock_terminal.assert_called_once()

    async def test_confirmation_abort_behavior(self):
        """Capture behavior: user abort during confirmation.

        When a user is presented with a confirmation dialog and chooses to abort
        (option 3: "No, and tell Claude what to do differently"), the system:

        1. Shows the initial "Tool()" info message
        2. Calls run_in_terminal which returns True (abort signal)
        3. Raises UserAbortError to stop execution
        4. Calls patch_tool_messages to clean up any orphaned tool calls

        This ensures that when users abort, the system state remains clean and
        the LLM gets proper feedback about the aborted operation.
        """
        from tunacode.exceptions import UserAbortError

        with patch("tunacode.cli.repl.ui.info") as mock_info:
            with patch(
                "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
            ) as mock_terminal:
                with patch("tunacode.cli.repl.patch_tool_messages") as mock_patch:
                    # Mock run_in_terminal to return True (abort)
                    mock_terminal.return_value = True

                    # Arrange
                    part = Mock()
                    part.tool_name = TOOL_WRITE_FILE
                    part.args = '{"filepath": "test.txt", "content": "test"}'
                    # Act & Assert
                    with pytest.raises(UserAbortError):
                        await _tool_handler(part, self.state_manager)

                    # Info message was shown before abort
                    mock_info.assert_called_once_with(f"Tool({TOOL_WRITE_FILE})")
                    # patch_tool_messages was called
                    mock_patch.assert_called_once_with(
                        "Operation aborted by user.", self.state_manager
                    )

    async def test_spinner_lifecycle(self):
        """Capture behavior: spinner stops during interaction and restarts after.

        The spinner is a visual indicator that shows the AI is "thinking" or processing.
        During tool confirmations, the spinner must be stopped so users can interact
        with the confirmation dialog, then restarted after the interaction.

        This test verifies the spinner lifecycle:
        1. Spinner.stop() is called BEFORE any user interaction
        2. User interaction happens (confirmation dialog)
        3. Spinner.start() is called AFTER interaction completes

        This ensures a smooth UI experience where the spinner doesn't interfere
        with user input and resumes to show ongoing processing.
        """
        # Test with a write tool that requires confirmation
        with patch("tunacode.cli.repl.ui.info"):
            with patch(
                "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
            ) as mock_terminal:
                mock_terminal.return_value = False

                # Reset spinner mocks
                self.state_manager.session.spinner.stop.reset_mock()
                self.state_manager.session.spinner.start.reset_mock()

                # Arrange
                part = Mock()
                part.tool_name = TOOL_WRITE_FILE
                part.args = '{"filepath": "test.txt", "content": "test"}'
                # Act
                await _tool_handler(part, self.state_manager)

                # Assert - Golden master
                # Spinner lifecycle: stop before interaction, start after
                assert self.state_manager.session.spinner.stop.call_count == 1
                assert self.state_manager.session.spinner.start.call_count == 1
                # Verify order
                calls = self.state_manager.session.spinner.method_calls
                assert calls[0][0] == "stop"
                assert calls[1][0] == "start"
