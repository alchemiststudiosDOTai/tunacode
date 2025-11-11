"""
Characterization tests for output display logic in process_request function.
Tests the complex nested conditionals around streaming vs non-streaming output.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import tunacode.cli.repl as repl_mod


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "streaming_enabled,result_obj,expected_ui_calls",
    [
        # Streaming enabled - should not display output (already shown)
        (True, MagicMock(result=MagicMock(output="test output")), {"agent": 0, "muted": 0}),
        # Non-streaming: No result object
        (False, MagicMock(result=None), {"agent": 0, "muted": 1}),
        # Non-streaming: No output attribute
        (False, MagicMock(result=MagicMock(spec=[])), {"agent": 0, "muted": 1}),
        # Non-streaming: String output (displayable)
        (False, MagicMock(result=MagicMock(output="Hello world")), {"agent": 1, "muted": 0}),
        # Non-streaming: JSON thought (not displayable)
        (
            False,
            MagicMock(result=MagicMock(output='{"thought": "test"}')),
            {"agent": 0, "muted": 0},
        ),
        # Non-streaming: Tool uses (not displayable)
        (False, MagicMock(result=MagicMock(output='{"tool_uses": []}')), {"agent": 0, "muted": 0}),
        # Non-streaming: Non-string output (not displayable)
        (False, MagicMock(result=MagicMock(output=123)), {"agent": 0, "muted": 0}),
    ],
)
async def test_process_request_output_display_logic(
    streaming_enabled, result_obj, expected_ui_calls
):
    """Test the complex output display logic in process_request."""

    state_manager = MagicMock()
    state_manager.session.current_model = "test-model"
    state_manager.session.user_config = {"settings": {"enable_streaming": streaming_enabled}}
    state_manager.session.show_thoughts = False
    state_manager.session.messages = []
    state_manager.session.files_in_context = set()
    state_manager.session.spinner = None
    state_manager.session.is_streaming_active = False

    # Mock UI calls
    ui_agent_mock = AsyncMock()
    ui_muted_mock = AsyncMock()
    ui_spinner_mock = AsyncMock()

    with (
        patch.object(repl_mod.ui, "agent", ui_agent_mock),
        patch.object(repl_mod.ui, "muted", ui_muted_mock),
        patch.object(repl_mod.ui, "spinner", ui_spinner_mock),
        patch.object(repl_mod.agent, "process_request", new=AsyncMock(return_value=result_obj)),
        patch("tunacode.utils.text_utils.expand_file_refs", return_value=("test input", [])),
    ):
        # Mock streaming panel for streaming tests
        if streaming_enabled:
            streaming_panel = AsyncMock()
            with patch.object(repl_mod.ui, "StreamingAgentPanel", return_value=streaming_panel):
                await repl_mod.process_request("test input", state_manager, output=True)
        else:
            await repl_mod.process_request("test input", state_manager, output=True)

        # Assert UI calls match expected behavior
        assert ui_agent_mock.call_count == expected_ui_calls["agent"]
        assert ui_muted_mock.call_count >= expected_ui_calls["muted"]  # May have additional calls
