"""
Golden baseline tests for ToolHandler authorization logic.

These tests capture the exact behavior of the current ToolHandler.should_confirm()
method before refactoring. They serve as regression tests to ensure the refactored
implementation maintains identical behavior.

Test Coverage:
1. present_plan special case (never confirm)
2. Plan mode blocking (force confirmation for write tools)
3. Read-only tools (skip confirmation)
4. Template allowed tools (skip confirmation)
5. YOLO mode (skip confirmation)
6. Tool ignore list (skip confirmation)
7. Default behavior (require confirmation)
8. Priority ordering of rules
"""

import pytest

from tunacode.core.state import StateManager
from tunacode.core.tool_handler import ToolHandler
from tunacode.templates.loader import Template


class TestPresentPlanSpecialCase:
    """Test present_plan tool never requires confirmation."""

    def test_present_plan_never_confirms_in_normal_mode(self):
        """present_plan should never require confirmation in normal mode."""
        state = StateManager()
        handler = ToolHandler(state)

        assert not handler.should_confirm("present_plan")

    def test_present_plan_never_confirms_even_without_yolo(self):
        """present_plan should skip confirmation even when YOLO is off."""
        state = StateManager()
        state.session.yolo = False
        handler = ToolHandler(state)

        assert not handler.should_confirm("present_plan")

    def test_present_plan_never_confirms_in_plan_mode(self):
        """present_plan should skip confirmation even in plan mode."""
        state = StateManager()
        state.enter_plan_mode()
        handler = ToolHandler(state)

        assert not handler.should_confirm("present_plan")


class TestPlanModeBlocking:
    """Test plan mode blocks write tools."""

    def test_write_tools_blocked_in_plan_mode(self):
        """Write tools should be blocked (require confirmation) in plan mode."""
        state = StateManager()
        state.enter_plan_mode()
        handler = ToolHandler(state)

        # Write tools should require confirmation in plan mode
        assert handler.should_confirm("write_file")
        assert handler.should_confirm("update_file")

    def test_execute_tools_blocked_in_plan_mode(self):
        """Execute tools should be blocked in plan mode."""
        state = StateManager()
        state.enter_plan_mode()
        handler = ToolHandler(state)

        assert handler.should_confirm("bash")
        assert handler.should_confirm("run_command")

    def test_read_only_tools_not_blocked_in_plan_mode(self):
        """Read-only tools should not be blocked in plan mode."""
        state = StateManager()
        state.enter_plan_mode()
        handler = ToolHandler(state)

        assert not handler.should_confirm("read_file")
        assert not handler.should_confirm("grep")
        assert not handler.should_confirm("list_dir")
        assert not handler.should_confirm("glob")
        assert not handler.should_confirm("react")
        assert not handler.should_confirm("exit_plan_mode")

    def test_plan_mode_overrides_yolo(self):
        """Plan mode blocking should override YOLO mode for write tools."""
        state = StateManager()
        state.session.yolo = True
        state.enter_plan_mode()
        handler = ToolHandler(state)

        # Even with YOLO, write tools should be blocked in plan mode
        assert handler.should_confirm("write_file")
        assert handler.should_confirm("bash")

    def test_plan_mode_overrides_tool_ignore_list(self):
        """Plan mode blocking should override tool ignore list for write tools."""
        state = StateManager()
        state.session.tool_ignore = ["write_file", "bash"]
        state.enter_plan_mode()
        handler = ToolHandler(state)

        # Even with ignore list, write tools should be blocked in plan mode
        assert handler.should_confirm("write_file")
        assert handler.should_confirm("bash")


class TestReadOnlyTools:
    """Test read-only tools never require confirmation."""

    def test_read_only_tools_skip_confirmation(self):
        """All read-only tools should skip confirmation."""
        state = StateManager()
        handler = ToolHandler(state)

        # READ_ONLY_TOOLS from constants
        assert not handler.should_confirm("read_file")
        assert not handler.should_confirm("grep")
        assert not handler.should_confirm("list_dir")
        assert not handler.should_confirm("glob")
        assert not handler.should_confirm("react")
        assert not handler.should_confirm("exit_plan_mode")

    def test_read_only_tools_skip_even_without_yolo(self):
        """Read-only tools should skip confirmation even when YOLO is off."""
        state = StateManager()
        state.session.yolo = False
        handler = ToolHandler(state)

        assert not handler.should_confirm("read_file")
        assert not handler.should_confirm("grep")


class TestTemplateAllowedTools:
    """Test template allowed tools skip confirmation."""

    def test_template_allowed_tools_skip_confirmation(self):
        """Tools in active template's allowed_tools should skip confirmation."""
        state = StateManager()
        handler = ToolHandler(state)

        # Create template with allowed tools
        template = Template(
            name="test_template",
            description="Test template",
            prompt="Test prompt",
            allowed_tools=["write_file", "bash"],
            parameters={},
            shortcut=None,
        )
        handler.set_active_template(template)

        # Allowed tools should skip confirmation
        assert not handler.should_confirm("write_file")
        assert not handler.should_confirm("bash")

    def test_template_non_allowed_tools_still_require_confirmation(self):
        """Tools not in template's allowed_tools should still require confirmation."""
        state = StateManager()
        state.session.yolo = False
        handler = ToolHandler(state)

        template = Template(
            name="test_template",
            description="Test template",
            prompt="Test prompt",
            allowed_tools=["write_file"],
            parameters={},
            shortcut=None,
        )
        handler.set_active_template(template)

        # write_file is allowed
        assert not handler.should_confirm("write_file")

        # bash is not in allowed_tools, should require confirmation
        assert handler.should_confirm("bash")

    def test_template_with_no_allowed_tools_requires_confirmation(self):
        """Template with None or empty allowed_tools should require confirmation."""
        state = StateManager()
        state.session.yolo = False
        handler = ToolHandler(state)

        # Template with no allowed_tools
        template = Template(
            name="test_template",
            description="Test template",
            prompt="Test prompt",
            allowed_tools=None,
            parameters={},
            shortcut=None,
        )
        handler.set_active_template(template)

        # Should require confirmation (except for read-only tools)
        assert handler.should_confirm("write_file")
        assert handler.should_confirm("bash")

    def test_no_active_template_requires_confirmation(self):
        """With no active template, tools should require confirmation."""
        state = StateManager()
        state.session.yolo = False
        handler = ToolHandler(state)

        # No template set
        assert handler.active_template is None

        # Should require confirmation
        assert handler.should_confirm("write_file")
        assert handler.should_confirm("bash")


class TestYoloMode:
    """Test YOLO mode skips all confirmations."""

    def test_yolo_mode_skips_confirmation(self):
        """YOLO mode should skip confirmation for all tools."""
        state = StateManager()
        state.session.yolo = True
        handler = ToolHandler(state)

        # All tools should skip confirmation in YOLO mode
        assert not handler.should_confirm("write_file")
        assert not handler.should_confirm("update_file")
        assert not handler.should_confirm("bash")
        assert not handler.should_confirm("run_command")

    def test_yolo_off_requires_confirmation(self):
        """With YOLO off, write tools should require confirmation."""
        state = StateManager()
        state.session.yolo = False
        handler = ToolHandler(state)

        # Write tools should require confirmation
        assert handler.should_confirm("write_file")
        assert handler.should_confirm("bash")


class TestToolIgnoreList:
    """Test tool ignore list skips confirmations."""

    def test_ignored_tools_skip_confirmation(self):
        """Tools in tool_ignore list should skip confirmation."""
        state = StateManager()
        state.session.yolo = False
        state.session.tool_ignore = ["write_file", "bash"]
        handler = ToolHandler(state)

        # Ignored tools should skip confirmation
        assert not handler.should_confirm("write_file")
        assert not handler.should_confirm("bash")

    def test_non_ignored_tools_require_confirmation(self):
        """Tools not in ignore list should require confirmation."""
        state = StateManager()
        state.session.yolo = False
        state.session.tool_ignore = ["write_file"]
        handler = ToolHandler(state)

        # write_file is ignored
        assert not handler.should_confirm("write_file")

        # bash is not ignored
        assert handler.should_confirm("bash")

    def test_empty_ignore_list_requires_confirmation(self):
        """Empty ignore list should require confirmation for write tools."""
        state = StateManager()
        state.session.yolo = False
        state.session.tool_ignore = []
        handler = ToolHandler(state)

        assert handler.should_confirm("write_file")
        assert handler.should_confirm("bash")


class TestDefaultBehavior:
    """Test default behavior when no special rules apply."""

    def test_default_requires_confirmation_for_write_tools(self):
        """By default, write tools should require confirmation."""
        state = StateManager()
        # Ensure no special modes are active
        state.session.yolo = False
        state.session.tool_ignore = []
        handler = ToolHandler(state)

        assert handler.should_confirm("write_file")
        assert handler.should_confirm("update_file")
        assert handler.should_confirm("bash")
        assert handler.should_confirm("run_command")

    def test_default_skips_confirmation_for_read_only_tools(self):
        """By default, read-only tools should skip confirmation."""
        state = StateManager()
        state.session.yolo = False
        state.session.tool_ignore = []
        handler = ToolHandler(state)

        assert not handler.should_confirm("read_file")
        assert not handler.should_confirm("grep")
        assert not handler.should_confirm("list_dir")


class TestPriorityOrdering:
    """Test priority ordering of authorization rules."""

    def test_present_plan_has_highest_priority(self):
        """present_plan should skip confirmation regardless of other settings."""
        state = StateManager()
        state.session.yolo = False
        state.session.tool_ignore = []
        state.enter_plan_mode()
        handler = ToolHandler(state)

        # Even in plan mode with YOLO off, present_plan should skip confirmation
        assert not handler.should_confirm("present_plan")

    def test_plan_mode_has_priority_over_yolo(self):
        """Plan mode blocking should have priority over YOLO mode."""
        state = StateManager()
        state.session.yolo = True
        state.enter_plan_mode()
        handler = ToolHandler(state)

        # Write tools should be blocked even with YOLO
        assert handler.should_confirm("write_file")

        # Read-only tools should still skip
        assert not handler.should_confirm("read_file")

    def test_plan_mode_has_priority_over_template(self):
        """Plan mode blocking should have priority over template permissions."""
        state = StateManager()
        state.enter_plan_mode()
        handler = ToolHandler(state)

        template = Template(
            name="test_template",
            description="Test template",
            prompt="Test prompt",
            allowed_tools=["write_file", "bash"],
            parameters={},
            shortcut=None,
        )
        handler.set_active_template(template)

        # Write tools should be blocked even with template permission
        assert handler.should_confirm("write_file")
        assert handler.should_confirm("bash")

    def test_read_only_has_priority_over_default(self):
        """Read-only tools should skip confirmation even without YOLO."""
        state = StateManager()
        state.session.yolo = False
        state.session.tool_ignore = []
        handler = ToolHandler(state)

        # Read-only tools should skip even when YOLO is off
        assert not handler.should_confirm("read_file")


class TestConfirmationRequestFactory:
    """Test confirmation request creation."""

    def test_create_confirmation_request_with_filepath(self):
        """Confirmation request should include filepath from args."""
        state = StateManager()
        handler = ToolHandler(state)

        args = {"filepath": "/path/to/file.py", "content": "test"}
        request = handler.create_confirmation_request("write_file", args)

        assert request.tool_name == "write_file"
        assert request.args == args
        assert request.filepath == "/path/to/file.py"

    def test_create_confirmation_request_without_filepath(self):
        """Confirmation request should handle missing filepath."""
        state = StateManager()
        handler = ToolHandler(state)

        args = {"command": "ls -la"}
        request = handler.create_confirmation_request("bash", args)

        assert request.tool_name == "bash"
        assert request.args == args
        assert request.filepath is None


class TestProcessConfirmation:
    """Test confirmation response processing."""

    def test_process_confirmation_approved(self):
        """Approved confirmation should return True."""
        state = StateManager()
        handler = ToolHandler(state)

        from tunacode.types import ToolConfirmationResponse

        response = ToolConfirmationResponse(approved=True)
        assert handler.process_confirmation(response, "write_file") is True

    def test_process_confirmation_rejected(self):
        """Rejected confirmation should return False."""
        state = StateManager()
        handler = ToolHandler(state)

        from tunacode.types import ToolConfirmationResponse

        response = ToolConfirmationResponse(approved=False)
        assert handler.process_confirmation(response, "write_file") is False

    def test_process_confirmation_aborted(self):
        """Aborted confirmation should return False."""
        state = StateManager()
        handler = ToolHandler(state)

        from tunacode.types import ToolConfirmationResponse

        response = ToolConfirmationResponse(approved=True, abort=True)
        assert handler.process_confirmation(response, "write_file") is False

    def test_process_confirmation_skip_future_adds_to_ignore_list(self):
        """skip_future should add tool to ignore list."""
        state = StateManager()
        handler = ToolHandler(state)

        from tunacode.types import ToolConfirmationResponse

        response = ToolConfirmationResponse(approved=True, skip_future=True)
        handler.process_confirmation(response, "write_file")

        assert "write_file" in state.session.tool_ignore

    def test_process_confirmation_rejection_creates_user_message(self):
        """Rejection should create user message for agent."""
        state = StateManager()
        handler = ToolHandler(state)

        from tunacode.types import ToolConfirmationResponse

        response = ToolConfirmationResponse(
            approved=False, abort=True, instructions="Use different approach"
        )
        handler.process_confirmation(response, "write_file")

        # Should have created a message
        assert len(state.session.messages) == 1
        message = state.session.messages[0]
        from tunacode.utils.message_utils import get_message_content

        content = get_message_content(message)
        assert "cancelled before running" in content
        assert "Use different approach" in content


class TestToolBlockingInPlanMode:
    """Test is_tool_blocked_in_plan_mode method."""

    def test_not_blocked_in_normal_mode(self):
        """No tools should be blocked in normal mode."""
        state = StateManager()
        handler = ToolHandler(state)

        assert not handler.is_tool_blocked_in_plan_mode("write_file")
        assert not handler.is_tool_blocked_in_plan_mode("bash")
        assert not handler.is_tool_blocked_in_plan_mode("read_file")

    def test_write_tools_blocked_in_plan_mode(self):
        """Write tools should be blocked in plan mode."""
        state = StateManager()
        state.enter_plan_mode()
        handler = ToolHandler(state)

        assert handler.is_tool_blocked_in_plan_mode("write_file")
        assert handler.is_tool_blocked_in_plan_mode("update_file")
        assert handler.is_tool_blocked_in_plan_mode("bash")
        assert handler.is_tool_blocked_in_plan_mode("run_command")

    def test_read_only_tools_not_blocked_in_plan_mode(self):
        """Read-only tools should not be blocked in plan mode."""
        state = StateManager()
        state.enter_plan_mode()
        handler = ToolHandler(state)

        assert not handler.is_tool_blocked_in_plan_mode("read_file")
        assert not handler.is_tool_blocked_in_plan_mode("grep")
        assert not handler.is_tool_blocked_in_plan_mode("list_dir")

    def test_present_plan_not_blocked_in_plan_mode(self):
        """present_plan should not be blocked in plan mode."""
        state = StateManager()
        state.enter_plan_mode()
        handler = ToolHandler(state)

        assert not handler.is_tool_blocked_in_plan_mode("present_plan")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
