"""Thinking-panel state management for TunaCode TUI."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.widgets import Static

    from tunacode.ui.app import TextualReplApp


def _editor_has_draft(app: TextualReplApp) -> bool:
    return bool(app.editor.value.strip())


def _has_recent_editor_keypress(app: TextualReplApp) -> bool:
    if not _editor_has_draft(app):
        return False
    last_keypress_at = app._last_editor_keypress_at
    if last_keypress_at <= 0.0:
        return False
    elapsed_ms = (time.monotonic() - last_keypress_at) * app.MILLISECONDS_PER_SECOND
    return elapsed_ms < app.THINKING_DEFER_AFTER_KEYPRESS_MS


def _current_thinking_throttle_ms(app: TextualReplApp) -> float:
    if _editor_has_draft(app):
        return app.THINKING_THROTTLE_WHILE_DRAFTING_MS
    return app.THINKING_THROTTLE_MS


def _thinking_widget(app: TextualReplApp) -> Static | None:
    widget = app._thinking_panel_widget
    if widget is None:
        return None
    return widget


def hide_thinking_output(app: TextualReplApp) -> None:
    """Hide the live thinking panel without removing the widget."""
    thinking_panel_widget = _thinking_widget(app)
    if thinking_panel_widget is None:
        return
    thinking_panel_widget.update("")
    thinking_panel_widget.remove_class("active")


def clear_thinking_state(app: TextualReplApp) -> None:
    """Reset thinking buffer and hide the widget."""
    app._current_thinking_text = ""
    app._last_thinking_update = 0.0
    hide_thinking_output(app)


def finalize_thinking_state_after_request(app: TextualReplApp) -> None:
    """After a request completes, persist a final thinking panel into chat history."""
    if not app.state_manager.session.show_thoughts:
        clear_thinking_state(app)
        return
    if not app._current_thinking_text:
        hide_thinking_output(app)
        return

    from tunacode.ui.renderers.thinking import render_thinking_panel

    thinking_content, thinking_panel_meta = render_thinking_panel(
        app._current_thinking_text,
        max_lines=app.THINKING_MAX_RENDER_LINES,
        max_chars=app.THINKING_MAX_RENDER_CHARS,
    )
    app.chat_container.write(thinking_content, expand=True, panel_meta=thinking_panel_meta)
    clear_thinking_state(app)


def refresh_thinking_output(app: TextualReplApp, force: bool = False) -> None:
    """Throttled render of the live thinking panel."""
    if not app.state_manager.session.show_thoughts:
        return
    if not app._current_thinking_text:
        hide_thinking_output(app)
        return

    thinking_panel_widget = _thinking_widget(app)
    if thinking_panel_widget is None:
        return

    now = time.monotonic()
    elapsed_ms = (now - app._last_thinking_update) * app.MILLISECONDS_PER_SECOND
    if not force and _has_recent_editor_keypress(app):
        return

    thinking_throttle_ms = _current_thinking_throttle_ms(app)
    if not force and elapsed_ms < thinking_throttle_ms:
        return

    from tunacode.ui.renderers.thinking import render_thinking_panel

    app._last_thinking_update = now
    thinking_content, thinking_panel_meta = render_thinking_panel(
        app._current_thinking_text,
        max_lines=app.THINKING_MAX_RENDER_LINES,
        max_chars=app.THINKING_MAX_RENDER_CHARS,
    )
    thinking_panel_widget.border_title = thinking_panel_meta.border_title
    thinking_panel_widget.border_subtitle = thinking_panel_meta.border_subtitle
    thinking_panel_widget.update(thinking_content)
    thinking_panel_widget.add_class("active")


async def thinking_callback(app: TextualReplApp, delta: str) -> None:
    """Accumulate thinking text and refresh the panel."""
    app._current_thinking_text += delta
    current_char_count = len(app._current_thinking_text)
    overflow_char_count = current_char_count - app.THINKING_BUFFER_CHAR_LIMIT
    if overflow_char_count > 0:
        app._current_thinking_text = app._current_thinking_text[overflow_char_count:]

    if not app.state_manager.session.show_thoughts:
        return

    refresh_thinking_output(app)
