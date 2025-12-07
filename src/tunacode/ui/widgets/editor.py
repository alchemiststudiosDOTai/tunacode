"""Editor widget for TunaCode REPL."""

from __future__ import annotations

from textual import events
from textual.binding import Binding
from textual.widgets import Input

from .messages import EditorSubmitRequested
from .status_bar import StatusBar


class Editor(Input):
    """Single-line editor with Enter to submit."""

    value: str  # type re-declaration for mypy (inherited reactive from Input)

    BINDINGS = [
        Binding("enter", "submit", "Submit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__(placeholder="we await...")
        self._placeholder_cleared: bool = False

    def on_key(self, event: events.Key) -> None:
        """Handle key events for confirmation and bash-mode auto-spacing."""
        if event.key in ("1", "2", "3"):
            app = self.app
            if (
                hasattr(app, "pending_confirmation")
                and app.pending_confirmation is not None
                and not app.pending_confirmation.future.done()
            ):
                event.prevent_default()
                return

        # Auto-insert space after ! prefix
        # When value is "!" and user types a non-space character,
        # insert space between ! and the character
        if self.value == "!" and event.character and event.character != " ":
            event.prevent_default()
            self.value = f"! {event.character}"
            self.cursor_position = len(self.value)

    def action_submit(self) -> None:
        text = self.value.strip()
        if not text:
            return

        self.post_message(EditorSubmitRequested(text=text, raw_text=self.value))
        self.value = ""

    def watch_value(self, value: str) -> None:
        """Toggle bash-mode class and clear placeholder on first input."""
        if value and not self._placeholder_cleared:
            self.placeholder = ""
            self._placeholder_cleared = True

        self.remove_class("bash-mode")
        try:
            status_bar = self.app.query_one(StatusBar)
        except Exception:
            return
        if value.startswith("!"):
            self.add_class("bash-mode")
            status_bar.set_mode("bash mode")
        else:
            status_bar.set_mode(None)
