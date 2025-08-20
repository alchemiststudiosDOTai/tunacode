"""
Module: tunacode.cli.commands.implementations.quickstart

QuickStart command implementation for interactive tutorial system.
Provides guided introduction to TunaCode for new users.
"""

import logging

from tunacode.types import CommandContext, CommandResult

from ..base import CommandCategory, CommandSpec, SimpleCommand

logger = logging.getLogger(__name__)


class QuickStartCommand(SimpleCommand):
    """Interactive quickstart tutorial command."""

    spec = CommandSpec(
        name="quickstart",
        aliases=["/quickstart", "/qs"],
        description="Interactive tutorial for getting started with TunaCode",
        category=CommandCategory.SYSTEM,
    )

    async def execute(self, _args: list[str], context: CommandContext) -> CommandResult:
        """Execute the quickstart tutorial."""
        try:
            from ....tutorial import TutorialManager
        except ImportError:
            await context.ui.error("Tutorial system is not available")
            return

        tutorial_manager = TutorialManager(context.state_manager)

        # Always run tutorial when explicitly requested
        success = await tutorial_manager.run_tutorial()

        if success:
            await context.ui.success("✅ Tutorial completed successfully!")
        else:
            await context.ui.info("Tutorial was cancelled or interrupted")
