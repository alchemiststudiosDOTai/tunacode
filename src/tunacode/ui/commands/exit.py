"""Exit command for exiting the REPL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


class ExitCommand(Command):
    """Close TunaCode from a slash command."""

    name = "exit"
    description = "Exit TunaCode"
    usage = "/exit"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        args = args.strip()
        if args:
            app.notify("Usage: /exit", severity="warning")
            return

        app.exit()
