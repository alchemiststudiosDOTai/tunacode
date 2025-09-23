"""Resume command: save and load chat sessions.

Implements `/resume save` and `/resume load <session_id>` using
JSON persistence in the per-session directory under ~/.tunacode.
"""

from __future__ import annotations

from typing import List, Optional

from ....types import CommandArgs, CommandContext, CommandResult
from ....ui import console as ui
from ....utils.session_utils import (
    load_session_state,
    save_session_state,
)
from ..base import CommandCategory, CommandSpec, SimpleCommand

USAGE = (
    "Usage:\n"
    "  /resume save                    Save current session state\n"
    "  /resume load <session_id>       Load a previously saved session\n"
)


class ResumeCommand(SimpleCommand):
    """Save and restore chat sessions."""

    spec = CommandSpec(
        name="resume",
        aliases=["/resume"],
        description="Save and restore chat sessions (manual persistence)",
        category=CommandCategory.SYSTEM,
    )

    async def execute(self, args: CommandArgs, context: CommandContext) -> CommandResult:
        if not args:
            await ui.error("Missing subcommand: 'save' or 'load'")
            await ui.muted(USAGE)
            return None

        sub = args[0].lower()
        if sub == "save":
            return await self._handle_save(context)
        if sub == "load":
            return await self._handle_load(args[1:], context)

        await ui.error(f"Unknown subcommand: {sub}")
        await ui.muted(USAGE)
        return None

    async def _handle_save(self, context: CommandContext) -> Optional[str]:
        try:
            out_path = save_session_state(context.state_manager)
        except Exception as e:
            await ui.error(str(e))
            return None

        await ui.success(
            f"Session saved: id={context.state_manager.session.session_id} -> {out_path}"
        )
        return None

    async def _handle_load(self, args: List[str], context: CommandContext) -> Optional[str]:
        if not args:
            await ui.error("Missing session_id for load")
            await ui.muted(USAGE)
            return None

        session_id = args[0]
        try:
            ok = load_session_state(context.state_manager, session_id)
        except Exception as e:
            await ui.error(str(e))
            return None

        if not ok:
            await ui.error("Session not found or no session_state.json present")
            return None

        await ui.success(f"Session loaded: id={context.state_manager.session.session_id}")
        return None
