"""Thoughts command for toggling the reasoning panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


class ThoughtsCommand(Command):
    """Toggle display of streaming thought content."""

    name = "thoughts"
    description = "Toggle thought panel"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        _ = args
        session = app.state_manager.session
        session.show_thoughts = not session.show_thoughts

        if session.show_thoughts:
            app._refresh_thinking_output(force=True)
            app.notify("Thought panel: ON")
            return

        app._hide_thinking_output()
        app.notify("Thought panel: OFF")
