"""Help command for listing available slash commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command
from tunacode.ui.styles import STYLE_PRIMARY

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


class HelpCommand(Command):
    """Display available commands in a table."""

    name = "help"
    description = "Show available commands"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from rich.table import Table

        from tunacode.ui.commands import COMMANDS

        table = Table(title="Commands", show_header=True)
        table.add_column("Command", style=STYLE_PRIMARY)
        table.add_column("Description")

        for name, cmd in COMMANDS.items():
            table.add_row(f"/{name}", cmd.description)

        table.add_row("!<cmd>", "Run shell command")
        table.add_row("exit", "Exit TunaCode (legacy bare command)")

        app.rich_log.write(table)
