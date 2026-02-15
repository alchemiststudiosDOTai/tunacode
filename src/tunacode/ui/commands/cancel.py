"""Command for canceling active request or shell command workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


class CancelCommand(Command):
    """Cancel an in-progress request, shell command, or modal operation."""

    name = "cancel"
    description = "Cancel current request or shell command"
    usage = "/cancel"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        if args.strip():
            app.notify("Usage: /cancel", severity="warning")
            return

        app.action_cancel_request()
