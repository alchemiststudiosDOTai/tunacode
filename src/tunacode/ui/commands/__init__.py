"""Slash command package for TunaCode REPL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command
from tunacode.ui.commands.cancel import CancelCommand
from tunacode.ui.commands.clear import ClearCommand
from tunacode.ui.commands.compact import CompactCommand
from tunacode.ui.commands.debug import DebugCommand
from tunacode.ui.commands.exit import ExitCommand
from tunacode.ui.commands.help import HelpCommand
from tunacode.ui.commands.model import ModelCommand
from tunacode.ui.commands.resume import ResumeCommand
from tunacode.ui.commands.theme import ThemeCommand
from tunacode.ui.commands.update import UpdateCommand

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


COMMANDS: dict[str, Command] = {
    "help": HelpCommand(),
    "cancel": CancelCommand(),
    "clear": ClearCommand(),
    "compact": CompactCommand(),
    "debug": DebugCommand(),
    "exit": ExitCommand(),
    "model": ModelCommand(),
    "theme": ThemeCommand(),
    "resume": ResumeCommand(),
    "update": UpdateCommand(),
}


async def handle_command(app: TextualReplApp, text: str) -> bool:
    """Handle a command if text starts with / or !.

    Returns True if command was handled, False otherwise.
    """

    if text.startswith("!"):
        app.start_shell_command(text[1:])
        return True

    if text.startswith("/"):
        parts = text[1:].split(maxsplit=1)
        cmd_name = parts[0].lower() if parts else ""
        cmd_args = parts[1] if len(parts) > 1 else ""

        if cmd_name in COMMANDS:
            await COMMANDS[cmd_name].execute(app, cmd_args)
            return True
        else:
            app.notify(f"Unknown command: /{cmd_name}", severity="warning")
            return True

    if text.lower() == "exit":
        app.exit()
        return True

    return False
