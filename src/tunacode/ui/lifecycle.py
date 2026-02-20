"""App lifecycle management for TunaCode TUI."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from rich.console import RenderableType

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


def on_mount(app: TextualReplApp) -> None:
    """Initialize app on mount - theme, session metadata, and start REPL or setup."""
    from tunacode.core.ui_api.constants import SUPPORTED_THEME_NAMES, THEME_NAME

    user_config = app.state_manager.session.user_config
    saved_theme = user_config.get("settings", {}).get("theme", THEME_NAME)
    if saved_theme not in SUPPORTED_THEME_NAMES:
        saved_theme = THEME_NAME
    app.theme = saved_theme

    # Initialize session persistence metadata
    from tunacode.core.ui_api.system_paths import get_project_id

    session = app.state_manager.session
    session.project_id = get_project_id()
    session.working_directory = os.getcwd()
    if not session.created_at:
        session.created_at = datetime.now(UTC).isoformat()

    def _on_setup_callback(completed: bool | None) -> None:
        _on_setup_complete(app, completed)

    if app._show_setup:
        from tunacode.ui.screens import SetupScreen

        app.push_screen(SetupScreen(app.state_manager), _on_setup_callback)
    else:
        _start_repl(app)


def _on_setup_complete(app: TextualReplApp, completed: bool | None) -> None:
    """Called when setup screen is dismissed."""
    if completed:
        app._update_resource_bar()
    _start_repl(app)


def _start_repl(app: TextualReplApp) -> None:
    """Initialize REPL components after setup."""
    from tunacode.core.logging import get_logger

    # Initialize logging with TUI callback
    logger = get_logger()
    logger.set_state_manager(app.state_manager)

    def _write_tui(renderable: RenderableType) -> None:
        app.chat_container.write(renderable)

    logger.set_tui_callback(_write_tui)

    app.set_focus(app.editor)
    app.run_worker(app._request_worker, exclusive=False)
    from tunacode.ui.slopgotchi import SLOPGOTCHI_AUTO_MOVE_INTERVAL_SECONDS

    app._slopgotchi_timer = app.set_interval(
        SLOPGOTCHI_AUTO_MOVE_INTERVAL_SECONDS,
        app._update_slopgotchi,
    )
    app._update_resource_bar()

    # Lazy import to avoid circular dependency
    from tunacode.ui.welcome import show_welcome

    show_welcome(app.chat_container)


async def on_unmount(app: TextualReplApp) -> None:
    """Save session before app exits."""
    if app._slopgotchi_timer is not None:
        app._slopgotchi_timer.stop()
        app._slopgotchi_timer = None
    await app.state_manager.save_session()
