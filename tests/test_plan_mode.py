"""Tests for Plan Mode functionality."""

from unittest.mock import AsyncMock

import pytest

from tunacode.cli.commands.implementations.plan import ExitPlanCommand, PlanCommand
from tunacode.core.state import StateManager
from tunacode.core.tool_handler import ToolHandler
from tunacode.tools.exit_plan_mode import ExitPlanModeTool
from tunacode.types import CommandContext, ToolConfirmationResponse
from tunacode.utils.message_utils import get_message_content


class TestPlanModeState:
    """Test plan mode state management."""

    def test_state_manager_plan_mode_methods(self):
        """Test plan mode state transitions."""
        state_manager = StateManager()

        # Initial state should not be in plan mode
        assert not state_manager.is_plan_mode()
        assert state_manager.session.plan_mode is False
        assert state_manager.session.current_plan is None
        assert state_manager.session.plan_approved is False

        # Enter plan mode
        state_manager.enter_plan_mode()
        assert state_manager.is_plan_mode()
        assert state_manager.session.plan_mode is True
        assert state_manager.session.current_plan is None
        assert state_manager.session.plan_approved is False

        # Set and get plan
        test_plan = {"title": "Test Plan", "overview": "Test overview"}
        state_manager.set_current_plan(test_plan)
        assert state_manager.get_current_plan() == test_plan

        # Approve plan
        state_manager.approve_plan()
        assert not state_manager.is_plan_mode()  # Should exit plan mode
        assert state_manager.session.plan_approved is True

        # Exit plan mode with plan
        state_manager.enter_plan_mode()
        exit_plan = {"title": "Exit Plan", "overview": "Exit overview"}
        state_manager.exit_plan_mode(exit_plan)
        assert not state_manager.is_plan_mode()
        assert state_manager.session.current_plan == exit_plan
        assert state_manager.session.plan_approved is False


class TestToolHandler:
    """Test tool handler plan mode integration."""

    def test_process_confirmation_honors_skip_future(self):
        state_manager = StateManager()
        tool_handler = ToolHandler(state_manager)
        response = ToolConfirmationResponse(approved=True, skip_future=True)

        should_proceed = tool_handler.process_confirmation(response, "bash")

        assert should_proceed is True
        assert "bash" in state_manager.session.tool_ignore

    def test_tool_blocking_in_plan_mode(self):
        """Test that write tools are blocked in plan mode."""
        state_manager = StateManager()
        tool_handler = ToolHandler(state_manager)

        # Test in normal mode - should not block
        assert not tool_handler.is_tool_blocked_in_plan_mode("write_file")
        assert not tool_handler.is_tool_blocked_in_plan_mode("read_file")

        # Enter plan mode
        state_manager.enter_plan_mode()

        # Test write tools are blocked
        assert tool_handler.is_tool_blocked_in_plan_mode("write_file")
        assert tool_handler.is_tool_blocked_in_plan_mode("update_file")
        assert tool_handler.is_tool_blocked_in_plan_mode("bash")
        assert tool_handler.is_tool_blocked_in_plan_mode("run_command")

        # Test read-only tools are not blocked
        assert not tool_handler.is_tool_blocked_in_plan_mode("read_file")
        assert not tool_handler.is_tool_blocked_in_plan_mode("grep")
        assert not tool_handler.is_tool_blocked_in_plan_mode("list_dir")
        assert not tool_handler.is_tool_blocked_in_plan_mode("glob")

    def test_process_confirmation_with_feedback_aborts_and_records_message(self):
        state_manager = StateManager()
        tool_handler = ToolHandler(state_manager)

        response = ToolConfirmationResponse(
            approved=False,
            abort=True,
            instructions="Use list_dir on src",
        )

        should_proceed = tool_handler.process_confirmation(response, "bash")

        assert should_proceed is False
        assert len(state_manager.session.messages) == 1
        recorded = state_manager.session.messages[0]
        assert "Use list_dir on src" in get_message_content(recorded)

    def test_should_confirm_in_plan_mode(self):
        """Test that blocked tools require confirmation (for blocking)."""
        state_manager = StateManager()
        tool_handler = ToolHandler(state_manager)

        # Normal mode - write tools might not require confirmation
        state_manager.session.yolo = True  # Skip confirmations normally
        assert not tool_handler.should_confirm("write_file")

        # Plan mode - blocked tools should force confirmation
        state_manager.enter_plan_mode()
        assert tool_handler.should_confirm("write_file")  # Force confirmation to show error
        assert not tool_handler.should_confirm(
            "read_file"
        )  # Read-only tools don't need confirmation


class TestPlanCommands:
    """Test plan mode commands."""

    @pytest.mark.asyncio
    async def test_plan_command(self):
        """Test /plan command."""
        state_manager = StateManager()
        context = CommandContext(state_manager=state_manager, process_request=AsyncMock())

        command = PlanCommand()

        # Should enter plan mode
        await command.execute([], context)
        assert state_manager.is_plan_mode()

    @pytest.mark.asyncio
    async def test_exit_plan_command(self):
        """Test /exit-plan command."""
        state_manager = StateManager()
        context = CommandContext(state_manager=state_manager, process_request=AsyncMock())

        command = ExitPlanCommand()

        # Should show warning when not in plan mode
        await command.execute([], context)
        assert not state_manager.is_plan_mode()  # Should remain false

        # Enter plan mode and then exit
        state_manager.enter_plan_mode()
        await command.execute([], context)
        assert not state_manager.is_plan_mode()


class TestExitPlanModeTool:
    """Test exit plan mode tool."""

    @pytest.mark.asyncio
    async def test_exit_plan_mode_tool_creation(self):
        """Test that the tool can be created with state manager."""
        state_manager = StateManager()
        tool = ExitPlanModeTool(state_manager=state_manager)

        assert tool.state_manager is state_manager
        assert tool.tool_name == "exit_plan_mode"

    @pytest.mark.asyncio
    async def test_plan_presentation_structure(self):
        """Test that plan presentation includes all required fields."""
        state_manager = StateManager()
        tool = ExitPlanModeTool(state_manager=state_manager)

        # Mock the user approval to avoid interactive input
        tool._get_user_approval = AsyncMock(return_value=True)

        # Enter plan mode
        state_manager.enter_plan_mode()

        # Execute the tool with a comprehensive plan
        result = await tool._execute(
            plan_title="Test Implementation Plan",
            overview="Test overview of the implementation",
            implementation_steps=[
                "Step 1: Analyze requirements",
                "Step 2: Design solution",
                "Step 3: Implement changes",
            ],
            files_to_modify=["file1.py", "file2.py"],
            files_to_create=["new_file.py"],
            risks_and_considerations=["Risk 1: Compatibility", "Risk 2: Performance"],
            testing_approach="Unit tests and integration tests",
            success_criteria=["All tests pass", "Performance benchmarks met"],
        )

        # Should have exited plan mode and stored the plan
        assert not state_manager.is_plan_mode()
        assert state_manager.get_current_plan() is not None
        assert "Plan approved" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
