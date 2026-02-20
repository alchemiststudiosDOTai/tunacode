"""Resume command for listing, loading, and deleting sessions."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


class ResumeCommand(Command):
    """Manage previous session restore and deletion."""

    name = "resume"
    description = "Resume a previous session"
    usage = "/resume [load <id>|delete <id>]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        parts = args.split(maxsplit=1) if args else []
        subcommand = parts[0].lower() if parts else ""

        handler = {
            "": self._handle_list,
            "list": self._handle_list,
            "load": self._handle_load,
            "delete": self._handle_delete,
        }.get(subcommand)

        if handler is None:
            app.notify(f"Unknown subcommand: {subcommand}", severity="warning")
            return

        await handler(app, parts)

    async def _handle_list(self, app: TextualReplApp, parts: list[str]) -> None:
        """Open the session picker UI."""
        from tunacode.ui.screens import SessionPickerScreen

        sessions = app.state_manager.list_sessions()
        if not sessions:
            app.notify("No saved sessions found")
            return

        current_session_id = app.state_manager.session.session_id

        def on_session_selected(session_id: str | None) -> None:
            if not session_id:
                return
            asyncio.create_task(self._load_session(app, session_id, sessions))

        app.push_screen(
            SessionPickerScreen(sessions, current_session_id),
            on_session_selected,
        )

    def _resolve_unique_session(
        self,
        app: TextualReplApp,
        parts: list[str],
        usage_hint: str,
    ) -> tuple[list[dict], dict] | None:
        """Resolve a unique session from a prefix argument.

        Returns (sessions, matched_session) or None if resolution fails.
        """

        if len(parts) < 2:
            app.notify(f"Usage: /resume {usage_hint}", severity="warning")
            return None

        session_id_prefix = parts[1].strip()
        sessions = app.state_manager.list_sessions()
        matching = [s for s in sessions if s["session_id"].startswith(session_id_prefix)]

        if not matching:
            app.notify(f"No session found matching: {session_id_prefix}", severity="error")
            return None
        if len(matching) > 1:
            app.notify("Multiple sessions match, be more specific", severity="warning")
            return None

        return sessions, matching[0]

    async def _handle_load(self, app: TextualReplApp, parts: list[str]) -> None:
        """Load a session by prefix."""
        resolved = self._resolve_unique_session(app, parts, "load <session-id>")
        if resolved is None:
            return
        sessions, target = resolved
        await self._load_session(app, target["session_id"], sessions)

    async def _handle_delete(self, app: TextualReplApp, parts: list[str]) -> None:
        """Delete a session by prefix."""
        from tunacode.core.ui_api.system_paths import delete_session_file

        resolved = self._resolve_unique_session(app, parts, "delete <session-id>")
        if resolved is None:
            return
        _sessions, target = resolved

        if target["session_id"] == app.state_manager.session.session_id:
            app.notify("Cannot delete current session", severity="error")
            return

        project_id = app.state_manager.session.project_id
        if delete_session_file(project_id, target["session_id"]):
            app.notify(f"Deleted session {target['session_id'][:8]}")
        else:
            app.notify("Failed to delete session", severity="error")

    async def _load_session(
        self,
        app: TextualReplApp,
        session_id: str,
        sessions: list[dict],
    ) -> None:
        """Load a session by ID."""
        from rich.text import Text

        target = next((s for s in sessions if s["session_id"] == session_id), None)
        if not target:
            app.notify("Session not found", severity="error")
            return

        await app.state_manager.save_session()

        if await app.state_manager.load_session(session_id):
            app.chat_container.clear()
            app._replay_session_messages()
            app._update_resource_bar()

            loaded_msg = Text()
            loaded_msg.append(
                f"Loaded session {session_id[:8]} ({target['message_count']} messages)\n",
                style="green",
            )
            app.chat_container.write(loaded_msg)
            app.notify("Session loaded")
        else:
            app.notify("Failed to load session", severity="error")
