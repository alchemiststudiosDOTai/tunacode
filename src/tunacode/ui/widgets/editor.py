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
        self._was_pasted: bool = False
        self._pasted_content: str = ""

    @property
    def _status_bar(self) -> StatusBar | None:
        """Get status bar or None if not available."""
        from textual.css.query import NoMatches

        try:
            return self.app.query_one(StatusBar)
        except NoMatches:
            return None

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
        # Use full pasted content if available, otherwise use input value
        if self._was_pasted and self._pasted_content:
            text = self._pasted_content.strip()
            raw_text = self._pasted_content
        else:
            text = self.value.strip()
            raw_text = self.value

        if not text:
            return

        self.post_message(
            EditorSubmitRequested(text=text, raw_text=raw_text, was_pasted=self._was_pasted)
        )
        self.value = ""
        self.placeholder = ""  # Reset placeholder after paste submit
        self._was_pasted = False
        self._pasted_content = ""

        # Reset StatusBar mode
        if status_bar := self._status_bar:
            status_bar.set_mode(None)

    def _on_paste(self, event: events.Paste) -> None:
        """Capture full paste content before Input truncates to first line."""
        lines = event.text.splitlines()
        line_count = len(lines)

        if line_count > 1:
            # Store full content for submission
            self._was_pasted = True
            self._pasted_content = event.text

            # Show paste indicator in Input
            self.value = f"[[PASTED {line_count} LINES]]"

            # Update StatusBar
            if status_bar := self._status_bar:
                status_bar.set_mode(f"pasted {line_count} lines")

            event.stop()  # Prevent parent from processing
        else:
            # Single line - let parent handle normally
            super()._on_paste(event)

    def watch_value(self, value: str) -> None:
        """React to value changes."""
        self._maybe_clear_placeholder(value)
        self._update_bash_mode(value)

    def _maybe_clear_placeholder(self, value: str) -> None:
        """Clear placeholder on first non-paste input."""
        if value and not self._placeholder_cleared and not self._was_pasted:
            self.placeholder = ""
            self._placeholder_cleared = True

    def _update_bash_mode(self, value: str) -> None:
        """Toggle bash-mode class and status bar indicator."""
        self.remove_class("bash-mode")

        if self._was_pasted:
            return

        if value.startswith("!"):
            self.add_class("bash-mode")

        if status_bar := self._status_bar:
            mode = "bash mode" if value.startswith("!") else None
            status_bar.set_mode(mode)
