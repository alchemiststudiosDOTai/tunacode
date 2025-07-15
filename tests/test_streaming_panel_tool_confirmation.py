"""Test streaming panel behavior during tool confirmations."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from tunacode.core.state import StateManager
from tunacode.core.tool_handler import ToolHandler
from tunacode.ui.panels import StreamingAgentPanel


@pytest.mark.asyncio
async def test_streaming_panel_stops_for_tool_confirmation():
    """Test that streaming panel stops before tool confirmation and resumes after."""
    state_manager = StateManager()

    # Mock streaming panel
    mock_streaming_panel = MagicMock(spec=StreamingAgentPanel)
    mock_streaming_panel.stop = AsyncMock()
    mock_streaming_panel.start = AsyncMock()

    # Set up state
    state_manager.session.is_streaming_active = True
    state_manager.session.streaming_panel = mock_streaming_panel
    state_manager.session.spinner = None  # No spinner when streaming

    # Import after setting up mocks
    from tunacode.cli.repl import _tool_handler

    # Mock tool call that needs confirmation
    mock_tool_call = Mock()
    mock_tool_call.tool_name = "write_file"
    mock_tool_call.args = '{"filepath": "test.txt", "content": "test"}'

    # Mock tool handler
    with patch.object(ToolHandler, "should_confirm", return_value=True):
        with patch.object(ToolHandler, "create_confirmation_request"):
            with patch.object(ToolHandler, "process_confirmation", return_value=True):
                with patch(
                    "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
                ) as mock_terminal:
                    # Mock run_in_terminal to return False (no abort)
                    mock_terminal.return_value = False

                    # Call tool handler
                    await _tool_handler(mock_tool_call, state_manager)

                    # Verify streaming panel was stopped before confirmation
                    mock_streaming_panel.stop.assert_called_once()

                    # Verify streaming panel was restarted after confirmation
                    mock_streaming_panel.start.assert_called_once()

                    # Verify stop was called before start
                    stop_call_order = mock_streaming_panel.stop.call_args_list[0][1].get(
                        "call_order", 0
                    )
                    start_call_order = mock_streaming_panel.start.call_args_list[0][1].get(
                        "call_order", 1
                    )
                    assert stop_call_order < start_call_order


@pytest.mark.asyncio
async def test_streaming_panel_not_affected_for_read_only_tools():
    """Test that streaming panel is not stopped for read-only tools."""
    state_manager = StateManager()

    # Mock streaming panel
    mock_streaming_panel = MagicMock(spec=StreamingAgentPanel)
    mock_streaming_panel.stop = AsyncMock()
    mock_streaming_panel.start = AsyncMock()

    # Set up state
    state_manager.session.is_streaming_active = True
    state_manager.session.streaming_panel = mock_streaming_panel
    state_manager.session.spinner = None
    state_manager.session.yolo = False
    state_manager.session.tool_ignore = []

    # Import after setting up mocks
    from tunacode.cli.repl import _tool_handler

    # Mock tool call that doesn't need confirmation (read-only)
    mock_tool_call = Mock()
    mock_tool_call.tool_name = "read_file"
    mock_tool_call.args = '{"file_path": "test.txt"}'

    # Mock tool handler
    with patch.object(ToolHandler, "should_confirm", return_value=False):
        with patch("tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock) as mock_terminal:
            # This shouldn't be called for read-only tools
            mock_terminal.return_value = False

            # Call tool handler
            await _tool_handler(mock_tool_call, state_manager)

            # Verify streaming panel was NOT stopped for read-only tools
            mock_streaming_panel.stop.assert_not_called()
            mock_streaming_panel.start.assert_not_called()


@pytest.mark.asyncio
async def test_streaming_panel_handled_when_none():
    """Test that code handles gracefully when streaming panel is None."""
    state_manager = StateManager()

    # Set up state with no streaming panel
    state_manager.session.is_streaming_active = True
    state_manager.session.streaming_panel = None  # No panel
    state_manager.session.spinner = None

    # Import after setting up mocks
    from tunacode.cli.repl import _tool_handler

    # Mock tool call
    mock_tool_call = Mock()
    mock_tool_call.tool_name = "write_file"
    mock_tool_call.args = '{"filepath": "test.txt", "content": "test"}'

    # Mock tool handler
    with patch.object(ToolHandler, "should_confirm", return_value=True):
        with patch.object(ToolHandler, "create_confirmation_request"):
            with patch.object(ToolHandler, "process_confirmation", return_value=True):
                with patch(
                    "tunacode.cli.repl.run_in_terminal", new_callable=AsyncMock
                ) as mock_terminal:
                    mock_terminal.return_value = False

                    # Should not raise any errors
                    await _tool_handler(mock_tool_call, state_manager)


@pytest.mark.asyncio
async def test_streaming_panel_lifecycle_in_process_request():
    """Test streaming panel lifecycle in the process_request function."""
    state_manager = StateManager()
    state_manager.session.user_config = {"settings": {"enable_streaming": True}}

    # Mock dependencies
    with patch("tunacode.cli.repl.ui") as mock_ui:
        mock_streaming_panel = MagicMock(spec=StreamingAgentPanel)
        mock_streaming_panel.start = AsyncMock()
        mock_streaming_panel.stop = AsyncMock()
        mock_streaming_panel.update = AsyncMock()

        mock_ui.StreamingAgentPanel.return_value = mock_streaming_panel
        mock_ui.spinner = AsyncMock(return_value=None)

        with patch("tunacode.cli.repl.agent.process_request", new_callable=AsyncMock) as mock_agent:
            # Mock successful agent response
            mock_result = Mock()
            mock_result.result = None
            mock_agent.return_value = mock_result

            from tunacode.cli.repl import process_request

            # Process a request
            await process_request("test request", state_manager)

            # Verify lifecycle
            assert not state_manager.session.is_streaming_active  # Should be reset after
            mock_streaming_panel.start.assert_called_once()
            mock_streaming_panel.stop.assert_called_once()

            # Verify panel was stored in session
            assert mock_agent.call_args[1]["streaming_callback"] is not None


if __name__ == "__main__":
    asyncio.run(test_streaming_panel_stops_for_tool_confirmation())
    asyncio.run(test_streaming_panel_not_affected_for_read_only_tools())
    asyncio.run(test_streaming_panel_handled_when_none())
    asyncio.run(test_streaming_panel_lifecycle_in_process_request())
    print("All streaming panel tests passed!")
