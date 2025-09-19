"""Test the task completion detection mechanism."""

from tunacode.core.agents.agent_components import check_task_completion
from tunacode.types import ResponseState


class TestCompletionDetection:
    """Test cases for task completion detection."""

    def test_check_task_completion_with_marker(self):
        """Test detection of completion marker."""
        content = """TUNACODE_TASK_COMPLETE
Fixed the import error in main.py."""

        is_complete, cleaned = check_task_completion(content)

        assert is_complete is True
        assert cleaned == "Fixed the import error in main.py."

    def test_check_task_completion_without_marker(self):
        """Test when no completion marker is present."""
        content = "Regular response without marker"

        is_complete, cleaned = check_task_completion(content)

        assert is_complete is False
        assert cleaned == content

    def test_check_task_completion_empty_content(self):
        """Test with empty content."""
        is_complete, cleaned = check_task_completion("")

        assert is_complete is False
        assert cleaned == ""

    def test_check_task_completion_marker_only(self):
        """Test with marker but no additional content."""
        content = "TUNACODE_TASK_COMPLETE"

        is_complete, cleaned = check_task_completion(content)

        assert is_complete is True
        assert cleaned == ""

    def test_check_task_completion_with_whitespace(self):
        """Test marker detection with surrounding whitespace."""
        content = """  TUNACODE_TASK_COMPLETE

The task has been completed successfully."""

        is_complete, cleaned = check_task_completion(content)

        assert is_complete is True
        assert cleaned == "The task has been completed successfully."

    def test_response_state_default(self):
        """Test ResponseState default values."""
        state = ResponseState()

        assert state.has_user_response is False
        assert state.has_final_synthesis is False
        assert state.task_completed is False

    def test_empty_response_continues(self):
        """Test that empty responses don't stop the agent."""
        # Empty content should not be considered complete
        is_complete, cleaned = check_task_completion("")
        assert is_complete is False

        # Response state should not have user response for empty content
        state = ResponseState()
        assert state.has_user_response is False

        # Even with whitespace, should not be complete without marker
        is_complete, cleaned = check_task_completion("   \n   \n   ")
        assert is_complete is False
