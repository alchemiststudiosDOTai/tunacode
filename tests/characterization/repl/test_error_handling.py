"""
Characterization tests for error handling in process_request function.
Tests all exception paths including the complex tool recovery logic.
"""

from asyncio.exceptions import CancelledError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior

import tunacode.cli.repl as repl_mod
from tunacode.exceptions import UserAbortError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception_type,expected_ui_call,expected_patch_call",
    [
        # CancelledError: Shows cancellation message, no patch
        (CancelledError(), "muted", False),
        # UserAbortError: Shows operation aborted message, no patch
        (UserAbortError("User cancelled"), "muted", False),
        # UnexpectedModelBehavior: Shows error message AND patches tool messages
        (UnexpectedModelBehavior("Model error"), "muted", True),
    ],
)
async def test_process_request_simple_error_handling(
    exception_type, expected_ui_call, expected_patch_call
):
    """Test simple error handling paths that don't involve tool recovery."""

    state_manager = MagicMock()
    state_manager.session.current_model = "test-model"
    state_manager.session.user_config = {"settings": {"enable_streaming": False}}
    state_manager.session.show_thoughts = False
    state_manager.session.messages = []
    state_manager.session.files_in_context = set()
    state_manager.session.spinner = None
    state_manager.session.is_streaming_active = False
    state_manager.session.current_task = None
    state_manager.session.input_sessions = {}

    # Mock UI calls
    ui_muted_mock = AsyncMock()
    ui_error_mock = AsyncMock()
    ui_spinner_mock = AsyncMock()
    patch_tool_messages_mock = MagicMock()

    with (
        patch.object(repl_mod.ui, "muted", ui_muted_mock),
        patch.object(repl_mod.ui, "error", ui_error_mock),
        patch.object(repl_mod.ui, "spinner", ui_spinner_mock),
        patch.object(repl_mod.agent, "process_request", new=AsyncMock(side_effect=exception_type)),
        patch("tunacode.utils.text_utils.expand_file_refs", return_value=("test input", [])),
        patch.object(repl_mod, "patch_tool_messages", patch_tool_messages_mock),
        patch("tunacode.cli.repl.run_in_terminal", new=AsyncMock()),
    ):
        await repl_mod.process_request("test input", state_manager, output=True)

        # Verify appropriate UI call was made
        if expected_ui_call == "muted":
            assert ui_muted_mock.call_count >= 1  # May have other calls
        elif expected_ui_call == "error":
            assert ui_error_mock.call_count >= 1

        # Verify patch_tool_messages behavior
        if expected_patch_call:
            assert patch_tool_messages_mock.call_count >= 1
        # Note: patch_tool_messages might be called for cleanup regardless


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_message,should_attempt_recovery,recovery_succeeds",
    [
        # Tool-related error keywords should trigger recovery attempt
        ("tool calling failed", True, True),
        ("function call error", True, False),
        ("schema validation failed", True, True),
        ("call parsing error", True, False),
        # Non-tool errors should not trigger recovery
        ("network timeout", False, False),
        ("memory error", False, False),
        ("syntax error", False, False),
    ],
)
async def test_process_request_tool_recovery_logic(
    error_message, should_attempt_recovery, recovery_succeeds
):
    """Test the complex tool recovery logic in the Exception handler."""

    state_manager = MagicMock()
    state_manager.session.current_model = "test-model"
    state_manager.session.user_config = {"settings": {"enable_streaming": False}}
    state_manager.session.show_thoughts = False
    state_manager.session.files_in_context = set()
    state_manager.session.spinner = None
    state_manager.session.is_streaming_active = False
    state_manager.session.current_task = None
    state_manager.session.input_sessions = {}

    # Set up message history for tool recovery
    if should_attempt_recovery:
        mock_part = MagicMock()
        mock_part.content = '{"tool": "read_file", "args": {"file_path": "test.txt"}}'

        mock_msg = MagicMock()
        mock_msg.parts = [mock_part]

        state_manager.session.messages = [mock_msg]
    else:
        state_manager.session.messages = []

    # Mock UI calls
    ui_error_mock = AsyncMock()
    ui_warning_mock = AsyncMock()
    ui_spinner_mock = AsyncMock()

    # Mock tool recovery function
    if recovery_succeeds:
        extract_tool_calls_mock = AsyncMock()  # Success - no exception
    else:
        extract_tool_calls_mock = AsyncMock(side_effect=Exception("Recovery failed"))

    with (
        patch.object(repl_mod.ui, "error", ui_error_mock),
        patch.object(repl_mod.ui, "warning", ui_warning_mock),
        patch.object(repl_mod.ui, "spinner", ui_spinner_mock),
        patch.object(
            repl_mod.agent, "process_request", new=AsyncMock(side_effect=Exception(error_message))
        ),
        patch("tunacode.utils.text_utils.expand_file_refs", return_value=("test input", [])),
        patch("tunacode.core.agents.main.extract_and_execute_tool_calls", extract_tool_calls_mock),
        patch("tunacode.cli.repl.run_in_terminal", new=AsyncMock()),
        patch.object(repl_mod, "patch_tool_messages"),
    ):
        await repl_mod.process_request("test input", state_manager, output=True)

        if should_attempt_recovery:
            # Should attempt tool recovery
            extract_tool_calls_mock.assert_called_once()

            if recovery_succeeds:
                # Should show recovery message and not show error
                ui_warning_mock.assert_called_with(" Recovered using JSON tool parsing")
                ui_error_mock.assert_not_called()
            else:
                # Recovery failed, should fall back to normal error handling
                ui_error_mock.assert_called_once()
                # Warning might or might not be called depending on timing
        else:
            # Should not attempt recovery, just show error
            extract_tool_calls_mock.assert_not_called()
            ui_error_mock.assert_called_once()
            ui_warning_mock.assert_not_called()


@pytest.mark.asyncio
async def test_process_request_tool_recovery_no_messages():
    """Test tool recovery when there are no messages in session."""

    state_manager = MagicMock()
    state_manager.session.current_model = "test-model"
    state_manager.session.user_config = {"settings": {"enable_streaming": False}}
    state_manager.session.show_thoughts = False
    state_manager.session.messages = []  # No messages
    state_manager.session.files_in_context = set()
    state_manager.session.spinner = None
    state_manager.session.is_streaming_active = False
    state_manager.session.current_task = None
    state_manager.session.input_sessions = {}

    ui_error_mock = AsyncMock()
    ui_warning_mock = AsyncMock()
    extract_tool_calls_mock = AsyncMock()

    with (
        patch.object(repl_mod.ui, "error", ui_error_mock),
        patch.object(repl_mod.ui, "warning", ui_warning_mock),
        patch.object(repl_mod.ui, "spinner", new=AsyncMock()),
        patch.object(
            repl_mod.agent,
            "process_request",
            new=AsyncMock(side_effect=Exception("tool call failed")),
        ),
        patch("tunacode.utils.text_utils.expand_file_refs", return_value=("test input", [])),
        patch("tunacode.core.agents.main.extract_and_execute_tool_calls", extract_tool_calls_mock),
        patch("tunacode.cli.repl.run_in_terminal", new=AsyncMock()),
        patch.object(repl_mod, "patch_tool_messages"),
    ):
        await repl_mod.process_request("test input", state_manager, output=True)

        # Should not attempt recovery when no messages
        extract_tool_calls_mock.assert_not_called()
        # Should fall back to normal error handling
        ui_error_mock.assert_called_once()
        ui_warning_mock.assert_not_called()


@pytest.mark.asyncio
async def test_process_request_tool_recovery_no_parts():
    """Test tool recovery when message has no parts attribute."""

    state_manager = MagicMock()
    state_manager.session.current_model = "test-model"
    state_manager.session.user_config = {"settings": {"enable_streaming": False}}
    state_manager.session.show_thoughts = False
    state_manager.session.files_in_context = set()
    state_manager.session.spinner = None
    state_manager.session.is_streaming_active = False
    state_manager.session.current_task = None
    state_manager.session.input_sessions = {}

    # Message without parts attribute
    mock_msg = MagicMock(spec=[])  # No parts attribute
    state_manager.session.messages = [mock_msg]

    ui_error_mock = AsyncMock()
    ui_warning_mock = AsyncMock()
    extract_tool_calls_mock = AsyncMock()

    with (
        patch.object(repl_mod.ui, "error", ui_error_mock),
        patch.object(repl_mod.ui, "warning", ui_warning_mock),
        patch.object(repl_mod.ui, "spinner", new=AsyncMock()),
        patch.object(
            repl_mod.agent,
            "process_request",
            new=AsyncMock(side_effect=Exception("function call error")),
        ),
        patch("tunacode.utils.text_utils.expand_file_refs", return_value=("test input", [])),
        patch("tunacode.core.agents.main.extract_and_execute_tool_calls", extract_tool_calls_mock),
        patch("tunacode.cli.repl.run_in_terminal", new=AsyncMock()),
        patch.object(repl_mod, "patch_tool_messages"),
    ):
        await repl_mod.process_request("test input", state_manager, output=True)

        # Should not attempt recovery when message has no parts
        extract_tool_calls_mock.assert_not_called()
        # Should fall back to normal error handling
        ui_error_mock.assert_called_once()
        ui_warning_mock.assert_not_called()
