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

    BASH_MODE_PREFIX = "!"
    BASH_MODE_PREFIX_WITH_SPACE = "! "
    PASTE_BUFFER_LONG_LINE_THRESHOLD: int = 400
    PASTE_BUFFER_SEPARATOR: str = "\n\n"

    BINDINGS = [
        Binding("enter", "submit", "Submit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__(placeholder="we await...")
        self._placeholder_cleared: bool = False
        self._was_pasted: bool = False
        self._pasted_content: str = ""
        self._paste_after_typed_text: bool = False

    @property
    def has_paste_buffer(self) -> bool:
        return bool(self._was_pasted and self._pasted_content)

    @property
    def paste_summary(self) -> str | None:
        if not self.has_paste_buffer:
            return None
        line_count = max(1, len(self._pasted_content.splitlines()))
        if line_count > 1:
            return f"pasted {line_count} lines"
        return f"pasted {len(self._pasted_content)} chars"

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

        has_paste_buffer = bool(getattr(self, "has_paste_buffer", False))
        if has_paste_buffer and not self.value and event.key == "backspace":
            event.prevent_default()
            self._clear_paste_buffer()
            return

        if event.character == self.BASH_MODE_PREFIX:
            if self.value.startswith(self.BASH_MODE_PREFIX):
                event.prevent_default()
                value = self.value[len(self.BASH_MODE_PREFIX) :]
                if value.startswith(" "):
                    value = value[1:]
                self.value = value
                self.cursor_position = len(self.value)
                return

            if not self.value:
                event.prevent_default()
                self.value = self.BASH_MODE_PREFIX_WITH_SPACE
                self.cursor_position = len(self.value)
                return

        # Auto-insert space after ! prefix
        # When value is "!" and user types a non-space character,
        # insert space between ! and the character
        if self.value == "!" and event.character and event.character != " ":
            event.prevent_default()
            self.value = f"! {event.character}"
            self.cursor_position = len(self.value)

    def clear_input(self) -> None:
        self.value = ""
        self._clear_paste_buffer()

    async def action_submit(self) -> None:
        submission = self._build_submission()
        if submission is None:
            return
        text, raw_text, was_pasted = submission

        self.post_message(
            EditorSubmitRequested(text=text, raw_text=raw_text, was_pasted=was_pasted)
        )
        self.value = ""
        self.placeholder = ""  # Reset placeholder after paste submit
        self._clear_paste_buffer()

        # Reset StatusBar mode
        if status_bar := self._status_bar:
            status_bar.set_mode(None)

    def _on_paste(self, event: events.Paste) -> None:
        """Capture full paste content before Input truncates to first line."""
        line_count = max(1, len(event.text.splitlines()))
        is_multiline = line_count > 1
        is_long_single_line = len(event.text) >= self.PASTE_BUFFER_LONG_LINE_THRESHOLD

        if not is_multiline and not is_long_single_line:
            super()._on_paste(event)
            return

        self._was_pasted = True
        self._pasted_content = event.text
        self._paste_after_typed_text = bool(self.value.strip())

        if paste_summary := self.paste_summary:
            self.placeholder = paste_summary
            if status_bar := self._status_bar:
                status_bar.set_mode(paste_summary)

        event.stop()

    def watch_value(self, value: str) -> None:
        """React to value changes."""
        self._maybe_clear_placeholder(value)
        self._update_bash_mode(value)

    def _maybe_clear_placeholder(self, value: str) -> None:
        """Clear placeholder on first non-paste input."""
        if value and not self._placeholder_cleared and not self.has_paste_buffer:
            self.placeholder = ""
            self._placeholder_cleared = True

    def _update_bash_mode(self, value: str) -> None:
        """Toggle bash-mode class and status bar indicator."""
        self.remove_class("bash-mode")

        if self.has_paste_buffer:
            return

        if value.startswith(self.BASH_MODE_PREFIX):
            self.add_class("bash-mode")

        if status_bar := self._status_bar:
            mode = "bash mode" if value.startswith(self.BASH_MODE_PREFIX) else None
            status_bar.set_mode(mode)

    def _clear_paste_buffer(self) -> None:
        previous_summary = self.paste_summary
        self._was_pasted = False
        self._pasted_content = ""
        self._paste_after_typed_text = False

        if previous_summary and self.placeholder == previous_summary:
            self.placeholder = ""

        self._update_bash_mode(self.value)

    def _build_submission(self) -> tuple[str, str, bool] | None:
        typed_text = self.value
        typed_has_content = bool(typed_text.strip())
        paste_text = self._pasted_content.rstrip("\n")
        paste_has_content = bool(paste_text.strip())

        if not typed_has_content and not paste_has_content:
            return None

        if not paste_has_content:
            text = typed_text.strip()
            return text, typed_text, False

        if not typed_has_content:
            return paste_text, paste_text, True

        typed_stripped = typed_text.strip()
        if self._paste_after_typed_text:
            combined = typed_stripped + self.PASTE_BUFFER_SEPARATOR + paste_text
        else:
            combined = paste_text + self.PASTE_BUFFER_SEPARATOR + typed_stripped

        return combined, combined, True
