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

            # Parse session ID to check if it's new format (timestamp-based)
            is_new_format = "_" in sid and len(sid.split("_")) >= 4

            if is_new_format:
                # New format: YYYY-MM-DD_HH-MM-SS_{slug}_{shortid}
                parts = sid.split("_")
                if len(parts) >= 4:
                    date_part = parts[0]
                    time_part = parts[1]
                    description = "_".join(parts[2:-1])  # Exclude the shortid suffix
                    shortid = parts[-1]
                    # Format as readable timestamp + description (+ shortid)
                    display_name = f"{date_part} {time_part.replace('-', ':')} — {description.replace('-', ' ')} ({shortid})"
                else:
                    display_name = sid
            else:
                # Legacy UUID format - show with timestamp
                from datetime import datetime

                ts = datetime.fromtimestamp(entry.get("mtime", 0.0)).isoformat(
                    sep=" ", timespec="seconds"
                )
                display_name = f"{sid}  @ {ts}"

            preview = entry.get("last_message")
            preview_str = f" — {preview}" if preview and not is_new_format else ""
            await ui.muted(f"  {i:2d}. {display_name}  [{model}{count_str}]{preview_str}")

        await ui.muted("\nLoad by index:   /resume load 1")
        await ui.muted("Load by id:      /resume load <session_id>")
        return None
