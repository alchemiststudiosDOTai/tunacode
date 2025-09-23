"""Resume command: save and load chat sessions.

Implements `/resume save` and `/resume load <session_id>` using
JSON persistence in the per-session directory under ~/.tunacode.
"""

from __future__ import annotations

from typing import List, Optional

from ....types import CommandArgs, CommandContext, CommandResult
from ....ui import console as ui
from ....utils.session_utils import (
    list_saved_sessions,
    load_session_state,
    save_session_state,
)
from ..base import CommandCategory, CommandSpec, SimpleCommand

USAGE = (
    "Usage:\n"
    "  /resume                 List saved sessions\n"
    "  /resume list            List saved sessions\n"
    "  /resume save            Save current session state\n"
    "  /resume load <id|#>     Load a saved session by id or index from list\n"
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
            return await self._handle_list(context)

        sub = args[0].lower()
        if sub == "list":
            return await self._handle_list(context)
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

        # Allow numeric index (1-based) from the latest list
        token = args[0]
        session_id = token
        if token.isdigit():
            index = int(token)
            sessions = list_saved_sessions()
            if index < 1 or index > len(sessions):
                await ui.error(f"Invalid index: {index}")
                return None
            session_id = sessions[index - 1]["session_id"]
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

    async def _handle_list(self, context: CommandContext) -> Optional[str]:
        sessions = list_saved_sessions()
        if not sessions:
            await ui.info("No saved sessions found")
            await ui.muted("Use '/resume save' to save the current session.")
            return None

        await ui.info("Saved sessions (most recent first):")
        for i, entry in enumerate(sessions, 1):
            sid = entry["session_id"]
            model = entry.get("model") or "?"
            count = entry.get("message_count")
            count_str = f", {count} messages" if isinstance(count, int) else ""
            from datetime import datetime

            ts = datetime.fromtimestamp(entry.get("mtime", 0.0)).isoformat(
                sep=" ", timespec="seconds"
            )
            preview = entry.get("last_message")
            preview_str = f" — {preview}" if preview else ""
            await ui.muted(f"  {i:2d}. {sid}  [{model}{count_str}]  @ {ts}{preview_str}")

        await ui.muted("\nLoad by index:   /resume load 1")
        await ui.muted("Load by id:      /resume load <session_id>")
        return None
