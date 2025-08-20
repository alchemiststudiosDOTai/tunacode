"""Command reload implementation."""

from pathlib import Path
from typing import List

from ....types import CommandContext
from ....ui import console as ui
from ..base import CommandCategory, CommandSpec, SimpleCommand


class CommandReloadCommand(SimpleCommand):
    """Reload slash commands to discover new commands."""

    spec = CommandSpec(
        name="command-reload",
        aliases=["/command-reload"],
        description="Reload slash commands to discover newly added commands",
        category=CommandCategory.DEVELOPMENT,
    )

    def __init__(self, command_registry=None):
        self._command_registry = command_registry

    async def execute(self, args: List[str], context: CommandContext) -> None:
        # Check if any command directories exist
        command_dirs = [
            Path(".tunacode/commands"),
            Path(".claude/commands"),
            Path.home() / ".tunacode/commands",
            Path.home() / ".claude/commands",
        ]

        dirs_exist = any(cmd_dir.exists() for cmd_dir in command_dirs)

        if not dirs_exist:
            await ui.info("No commands directory found")
            return

        # Reload commands using registry
        if self._command_registry:
            try:
                self._command_registry.reload_slash_commands()
                await ui.success("Commands reloaded")
                return
            except Exception as e:
                await ui.error(f"Reload failed: {e}")
        else:
            await ui.error("Command registry not available")
