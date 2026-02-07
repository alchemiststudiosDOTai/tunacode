"""Session picker modal screen for TunaCode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

PREVIEW_MESSAGE_LIMIT: int = 3
PREVIEW_MAX_CHARS: int = 60
PREVIEW_ELLIPSIS: str = "..."
PREVIEW_TRUNCATE_CHARS: int = PREVIEW_MAX_CHARS - len(PREVIEW_ELLIPSIS)


class SessionPickerScreen(Screen[str | None]):
    """Modal screen for session selection with message preview."""

    CSS = """
    SessionPickerScreen {
        align: center middle;
    }

    #session-container {
        width: 70;
        height: auto;
        max-height: 24;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #session-title {
        text-style: bold;
        color: $accent;
        text-align: center;
        margin-bottom: 1;
    }

    #session-list {
        height: auto;
        max-height: 12;
    }

    #session-preview {
        height: 6;
        margin-top: 1;
        border-top: solid $primary;
        padding-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        sessions: list[dict[str, Any]],
        current_session_id: str,
    ) -> None:
        super().__init__()
        self._sessions = sessions
        self._current_session_id = current_session_id
        self._session_map: dict[str, dict[str, Any]] = {s["session_id"]: s for s in sessions}

    def compose(self) -> ComposeResult:
        options: list[Option] = []
        highlight_index = 0

        for i, session in enumerate(self._sessions):
            session_id = session["session_id"]
            short_id = session_id[:8]
            msg_count = session.get("message_count", 0)
            model = session.get("current_model", "unknown")
            if "/" in model:
                model = model.split("/")[-1]
            last_mod = session.get("last_modified", "")[:10]

            is_current = session_id == self._current_session_id
            current_marker = " (current)" if is_current else ""

            label = f"{short_id}{current_marker} | {msg_count} msgs | {model} | {last_mod}"
            options.append(Option(label, id=session_id))

            if is_current:
                highlight_index = i

        with Vertical(id="session-container"):
            yield Static("Resume Session", id="session-title")
            option_list = OptionList(*options, id="session-list")
            if options:
                option_list.highlighted = highlight_index
            yield option_list
            yield Static("Select a session to preview", id="session-preview")

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Show preview of messages when highlighting a session."""
        preview_widget = self.query_one("#session-preview", Static)

        if not event.option or not event.option.id:
            preview_widget.update("Select a session to preview")
            return

        session_id = str(event.option.id)
        session_data = self._session_map.get(session_id)
        if not session_data:
            preview_widget.update("Session not found")
            return

        file_path = session_data.get("file_path")
        if not file_path:
            preview_widget.update("No preview available")
            return

        preview_text = self._load_preview(Path(file_path))
        preview_widget.update(preview_text)

    def _load_preview(self, file_path: Path) -> str:
        """Load first 3 user messages from session file for preview."""
        try:
            with open(file_path) as f:
                data = json.load(f)
        except Exception:
            return "Could not load preview"

        messages = data.get("messages", [])
        previews: list[str] = []

        for msg in messages:
            if len(previews) >= PREVIEW_MESSAGE_LIMIT:
                break

            if not isinstance(msg, dict):
                continue

            content = self._extract_user_content(msg)
            if not content:
                continue

            preview = content
            if len(preview) > PREVIEW_MAX_CHARS:
                preview = preview[:PREVIEW_TRUNCATE_CHARS] + PREVIEW_ELLIPSIS

            previews.append(f"> {preview}")

        if not previews:
            return "No messages to preview"

        return "\n".join(previews)

    def _extract_user_content(self, msg: dict[str, Any]) -> str:
        """Extract user prompt content from a stored tinyagent message."""

        if msg.get("role") != "user":
            return ""

        from tunacode.core.ui_api.messaging import get_content

        return get_content(msg)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Confirm selection and dismiss with session ID."""
        if event.option and event.option.id:
            self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)
