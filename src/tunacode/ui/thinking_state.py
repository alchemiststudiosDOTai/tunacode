"""Thinking-panel state management for TunaCode TUI."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


def hide_thinking_output(app: TextualReplApp) -> None:
    """Remove the thinking panel widget from the DOM."""
    thinking_panel_widget = app._thinking_panel_widget
    if thinking_panel_widget is None:
        return

    app._thinking_panel_widget = None
    if thinking_panel_widget.parent is None:
        return

    thinking_panel_widget.remove()


def clear_thinking_state(app: TextualReplApp) -> None:
    """Reset thinking buffer and remove the widget."""
    app._current_thinking_text = ""
    app._last_thinking_update = 0.0
    hide_thinking_output(app)


def finalize_thinking_state_after_request(app: TextualReplApp) -> None:
    """After a request completes, either clear or force-render the thinking panel."""
    if not app.state_manager.session.show_thoughts:
        clear_thinking_state(app)
        return
    refresh_thinking_output(app, force=True)


def refresh_thinking_output(app: TextualReplApp, force: bool = False) -> None:
    """Throttled render of the thinking panel into the chat container."""
    if not app.state_manager.session.show_thoughts:
        return
    if not app._current_thinking_text:
        hide_thinking_output(app)
        return

    thinking_panel_widget = app._thinking_panel_widget
    is_first_render = thinking_panel_widget is None
    now = time.monotonic()
    elapsed_ms = (now - app._last_thinking_update) * app.MILLISECONDS_PER_SECOND
    if not force and not is_first_render and elapsed_ms < app.THINKING_THROTTLE_MS:
        return

    from tunacode.ui.renderers.thinking import render_thinking_panel

    app._last_thinking_update = now
    thinking_content, thinking_panel_meta = render_thinking_panel(
        app._current_thinking_text,
        max_lines=app.THINKING_MAX_RENDER_LINES,
        max_chars=app.THINKING_MAX_RENDER_CHARS,
    )

    if thinking_panel_widget is None:
        app._thinking_panel_widget = app.chat_container.write(
            thinking_content,
            expand=True,
            panel_meta=thinking_panel_meta,
        )
        return

    thinking_panel_widget.update(thinking_content)
    app.chat_container.scroll_end(animate=False)


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
