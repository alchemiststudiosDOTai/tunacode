"""Plan mode commands for TunaCode."""

from typing import List

from ....types import CommandContext
from ....ui import console as ui
from ..base import Command, CommandCategory, CommandSpec, SimpleCommand


class PlanCommand(SimpleCommand):
    """Enter plan mode for read-only research and planning."""
    
    spec = CommandSpec(
        name="plan",
        aliases=["/plan"],
        description="Enter Plan Mode - read-only research phase",
        category=CommandCategory.DEVELOPMENT,
    )
    
    async def execute(self, args: List[str], context: CommandContext) -> None:
        """Enter plan mode."""
        context.state_manager.enter_plan_mode()
        
        await ui.info("🔍 Entering Plan Mode")
        await ui.info("• Only read-only operations available")
        await ui.info("• Use tools to research and analyze the codebase")
        await ui.info("• Use 'exit_plan_mode' tool to present your plan")
        await ui.info("• Read-only tools: read_file, grep, list_dir, glob")
        await ui.success("✅ Plan Mode active - indicator will appear above next input")


class ExitPlanCommand(SimpleCommand):
    """Exit plan mode manually."""
    
    spec = CommandSpec(
        name="exit-plan",
        aliases=["/exit-plan"],
        description="Exit Plan Mode and return to normal mode",
        category=CommandCategory.DEVELOPMENT,
    )
    
    async def execute(self, args: List[str], context: CommandContext) -> None:
        """Exit plan mode manually."""
        if not context.state_manager.is_plan_mode():
            await ui.warning("Not currently in Plan Mode")
            return
        
        context.state_manager.exit_plan_mode()
        await ui.success("🚪 Exiting Plan Mode - returning to normal mode")
        await ui.info("✅ All tools are now available - '⏸ PLAN MODE ON' status removed")