"""
Tests for tool handler UI message behavior.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from tunacode.cli.repl import _tool_handler
from tunacode.constants import TOOL_GREP, TOOL_LIST_DIR, TOOL_READ_FILE, TOOL_WRITE_FILE


class TestToolHandlerUIMessages:
    """Test that tool handler shows UI messages appropriately."""

    @pytest.mark.asyncio
    async def test_read_only_tools_skip_tool_info_message(self):
        """Test that read-only tools don't show the Tool(name) info message."""
        # Setup mocks
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.yolo = False
        state_manager.session.tool_ignore = []
        state_manager.session.spinner = Mock()
        state_manager.session.spinner.stop = Mock()
        state_manager.session.spinner.start = Mock()
        state_manager.session.is_streaming_active = False
        state_manager.session.streaming_panel = None

        # Mock UI functions
        with patch("tunacode.cli.repl.ui.info") as mock_info:
            with patch(
                "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
            ) as mock_terminal:
                # Mock run_in_terminal to return False (no abort)
                mock_terminal.return_value = False

                # Test read-only tools
                for tool_name in [TOOL_READ_FILE, TOOL_GREP, TOOL_LIST_DIR]:
                    mock_info.reset_mock()

                    part = Mock()
                    part.tool_name = tool_name
                    part.args = "{}"

                    await _tool_handler(part, state_manager)

                    # Should NOT have called ui.info for read-only tools
                    mock_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_tools_show_tool_info_message(self):
        """Test that write/execute tools show the Tool(name) info message."""
        # Setup mocks
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.yolo = False
        state_manager.session.tool_ignore = []
        state_manager.session.spinner = Mock()
        state_manager.session.spinner.stop = Mock()
        state_manager.session.spinner.start = Mock()
        state_manager.session.is_streaming_active = False
        state_manager.session.streaming_panel = None

        # Mock UI functions
        with patch("tunacode.cli.repl.ui.info") as mock_info:
            with patch(
                "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
            ) as mock_terminal:
                # Mock run_in_terminal to return False (no abort)
                mock_terminal.return_value = False

                # Test write tool
                part = Mock()
                part.tool_name = TOOL_WRITE_FILE
                part.args = '{"filepath": "test.txt", "content": "test"}'

                await _tool_handler(part, state_manager)

                # Should have called ui.info for write tools
                mock_info.assert_called_once_with(f"Tool({TOOL_WRITE_FILE})")

    @pytest.mark.asyncio
    async def test_yolo_mode_still_skips_message_for_read_only(self):
        """Test that even in yolo mode, read-only tools don't show the message."""
        # Setup mocks
        state_manager = Mock()
        state_manager.session = Mock()
        state_manager.session.yolo = True  # Enable yolo mode
        state_manager.session.tool_ignore = []
        state_manager.session.spinner = Mock()
        state_manager.session.spinner.stop = Mock()
        state_manager.session.spinner.start = Mock()
        state_manager.session.is_streaming_active = False
        state_manager.session.streaming_panel = None

        # Mock UI functions
        with patch("tunacode.cli.repl.ui.info") as mock_info:
            with patch(
                "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
            ) as mock_terminal:
                # Mock run_in_terminal to return False (no abort)
                mock_terminal.return_value = False

                # Test read-only tool in yolo mode
                part = Mock()
                part.tool_name = TOOL_READ_FILE
                part.args = '{"filepath": "test.txt"}'

                await _tool_handler(part, state_manager)

                # Should NOT have called ui.info even in yolo mode for read-only tools
                mock_info.assert_not_called()
