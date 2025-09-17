"""Tests for agent output formatting to ensure clean display without JSON artifacts."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tunacode.cli.repl import execute_repl_request
from tunacode.types import SimpleResult


class TestAgentOutputFormatting:
    """Test that agent output is properly formatted for users."""

    def _create_mock_state_manager(self):
        """Create a properly configured mock StateManager."""
        state_manager = MagicMock()
        state_manager.session = MagicMock()
        state_manager.session.messages = []
        state_manager.session.show_thoughts = False
        state_manager.session.user_config = {"settings": {"enable_streaming": False}}
        state_manager.session.spinner = None
        state_manager.session.files_in_context = set()
        state_manager.session.is_streaming_active = False
        state_manager.is_plan_mode = MagicMock(return_value=False)
        return state_manager

    @pytest.mark.asyncio
    async def test_agent_output_without_json_thoughts(self):
        """Agent should return clean formatted text without JSON thought artifacts."""
        # Arrange
        state_manager = self._create_mock_state_manager()

        # Mock agent response with JSON thought that should be filtered
        mock_response = MagicMock()
        mock_response.result = SimpleResult(
            output='{"thought": "Reviewing the current JavaScript code..."}\n'
            '{"suggestions": ["1. Add comments to functions", "2. Use consistent error handling"]}'
        )

        with patch(
            "tunacode.cli.repl.agent.process_request", new_callable=AsyncMock
        ) as mock_process:
            mock_process.return_value = mock_response
            with patch("tunacode.cli.repl.ui.agent", new_callable=AsyncMock) as mock_ui_agent:
                # Act
                await execute_repl_request("Review my code", state_manager, output=True)

                # Assert - UI should NOT be called since JSON output is filtered
                mock_ui_agent.assert_not_called()

    @pytest.mark.asyncio
    async def test_agent_clean_text_output_displayed(self):
        """Clean text output from agent should be displayed to user."""
        # Arrange
        state_manager = self._create_mock_state_manager()

        # Mock agent response with clean text
        expected_output = "Here are my suggestions for improving your code:\n1. Add comments\n2. Improve error handling"
        mock_response = MagicMock()
        mock_response.result = SimpleResult(output=expected_output)

        with patch(
            "tunacode.cli.repl.agent.process_request", new_callable=AsyncMock
        ) as mock_process:
            mock_process.return_value = mock_response
            with patch("tunacode.cli.repl.ui.agent", new_callable=AsyncMock) as mock_ui_agent:
                # Act
                await execute_repl_request("Review my code", state_manager, output=True)

                # Assert - Clean text should be displayed
                mock_ui_agent.assert_called_once_with(expected_output)

    @pytest.mark.asyncio
    async def test_formatted_suggestions_without_json_wrapper(self):
        """Agent should format suggestions as clean text, not JSON."""
        # Arrange
        state_manager = self._create_mock_state_manager()

        # Expected clean formatted output
        expected_output = """Code Review Results:

The JavaScript code has a good structure with clear separation of concerns. Here are some suggestions for improvement:

1. **Add comments to functions** - Document the purpose and parameters of major functions for better maintainability.

2. **Consistent error handling** - Use try-catch blocks consistently and provide user-friendly error messages instead of alerts.

3. **Form validation** - Implement validation before submitting to ensure required fields are properly filled.

4. **Debounce input handlers** - Consider debouncing the updateSubmitButtonState function to prevent excessive calls.

5. **Accessibility improvements** - Add ARIA labels and ensure keyboard navigation works properly.

These changes will improve code maintainability and user experience."""

        mock_response = MagicMock()
        mock_response.result = SimpleResult(output=expected_output)

        with patch(
            "tunacode.cli.repl.agent.process_request", new_callable=AsyncMock
        ) as mock_process:
            mock_process.return_value = mock_response
            with patch("tunacode.cli.repl.ui.agent", new_callable=AsyncMock) as mock_ui_agent:
                # Act
                await execute_repl_request("Review my JavaScript code", state_manager, output=True)

                # Assert - Formatted text should be displayed
                mock_ui_agent.assert_called_once_with(expected_output)
