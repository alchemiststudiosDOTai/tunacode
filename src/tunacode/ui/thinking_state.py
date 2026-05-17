"""Thinking-panel state management for TunaCode TUI."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.widgets import Static

    from tunacode.ui.app import TextualReplApp


class ThinkingState:
    """Encapsulates live thinking-panel state and rendering logic."""

    def __init__(self, app: TextualReplApp) -> None:
        self._app = app
        self._text: str = ""
        self._last_update: float = 0.0

    @property
    def _widget(self) -> Static | None:
        widget = self._app._thinking_panel_widget
        if widget is None:
            return None
        return widget

    def _editor_has_draft(self) -> bool:
        return bool(self._app.editor.value.strip())

    def _has_recent_editor_keypress(self) -> bool:
        if not self._editor_has_draft():
            return False
        last_keypress_at = self._app._last_editor_keypress_at
        if last_keypress_at <= 0.0:
            return False
        elapsed_ms = (time.monotonic() - last_keypress_at) * self._app.MILLISECONDS_PER_SECOND
        return elapsed_ms < self._app.THINKING_DEFER_AFTER_KEYPRESS_MS

    def _throttle_ms(self) -> float:
        if self._editor_has_draft():
            return self._app.THINKING_THROTTLE_WHILE_DRAFTING_MS
        return self._app.THINKING_THROTTLE_MS

    def hide(self) -> None:
        """Hide the live thinking panel without removing the widget."""
        widget = self._widget
        if widget is None:
            return
        widget.update("")
        widget.remove_class("active")

    def clear(self) -> None:
        """Reset thinking buffer and hide the widget."""
        self._text = ""
        self._last_update = 0.0
        self.hide()

    def refresh(self, force: bool = False) -> None:
        """Throttled render of the live thinking panel."""
        if not self._app.state_manager.session.show_thoughts:
            return
        if not self._text:
            self.hide()
            return

        widget = self._widget
        if widget is None:
            return

        if not force and self._has_recent_editor_keypress():
            return

        now = time.monotonic()
        elapsed_ms = (now - self._last_update) * self._app.MILLISECONDS_PER_SECOND
        if not force and elapsed_ms < self._throttle_ms():
            return

        from tunacode.ui.renderers.thinking import render_thinking_panel

        self._last_update = now
        content, meta = render_thinking_panel(
            self._text,
            max_lines=self._app.THINKING_MAX_RENDER_LINES,
            max_chars=self._app.THINKING_MAX_RENDER_CHARS,
        )
        widget.border_title = meta.border_title
        widget.border_subtitle = meta.border_subtitle
        widget.update(content)
        widget.add_class("active")

    def finalize(self) -> None:
        """After a request completes, persist a final thinking panel into chat history."""
        if not self._app.state_manager.session.show_thoughts:
            self.clear()
            return
        if not self._text:
            self.hide()
            return

        from tunacode.ui.renderers.thinking import render_thinking_panel

        content, meta = render_thinking_panel(
            self._text,
            max_lines=self._app.THINKING_MAX_RENDER_LINES,
            max_chars=self._app.THINKING_MAX_RENDER_CHARS,
        )
        self._app.chat_container.write(content, expand=True, panel_meta=meta)
        self.clear()

    async def callback(self, delta: str) -> None:
        """Accumulate thinking text and refresh the panel."""
        self._text += delta
        overflow = len(self._text) - self._app.THINKING_BUFFER_CHAR_LIMIT
        if overflow > 0:
            self._text = self._text[overflow:]

        if not self._app.state_manager.session.show_thoughts:
            return

        self.refresh()
