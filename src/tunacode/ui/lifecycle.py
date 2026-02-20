"""App lifecycle management for TunaCode TUI."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from rich.console import RenderableType

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


class AppLifecycle:
    """Manage TunaCode app lifecycle stages."""

    def __init__(self, app: TextualReplApp) -> None:
        self._app = app
        self._state_manager = app.state_manager
        self._repl_started: bool = False

    def mount(self) -> None:
        """Initialize app on mount."""
        self._init_theme()
        self._init_session_metadata()

        if self._app._show_setup:
            self._push_setup_screen()
            return

        self._start_repl()

    async def unmount(self) -> None:
        """Save session and cleanup app resources before exit."""
        self._stop_slopgotchi_timer()
        await self._state_manager.save_session()

    def _init_theme(self) -> None:
        """Load and apply a supported theme from user settings."""
        from tunacode.core.ui_api.constants import SUPPORTED_THEME_NAMES, THEME_NAME

        user_config = self._state_manager.session.user_config
        saved_theme = user_config.get("settings", {}).get("theme", THEME_NAME)
        if saved_theme not in SUPPORTED_THEME_NAMES:
            self._app.theme = THEME_NAME
            return
        self._app.theme = saved_theme

    def _init_session_metadata(self) -> None:
        """Initialize persisted session metadata for this app launch."""
        from tunacode.core.ui_api.system_paths import get_project_id

        session = self._state_manager.session
        session.project_id = get_project_id()
        session.working_directory = os.getcwd()
        if session.created_at:
            return
        session.created_at = datetime.now(UTC).isoformat()

    def _push_setup_screen(self) -> None:
        """Show setup wizard and continue startup when dismissed."""
        from tunacode.ui.screens import SetupScreen

        setup_screen = SetupScreen(self._state_manager)
        self._app.push_screen(setup_screen, self._on_setup_complete)

    def _on_setup_complete(self, completed: bool | None) -> None:
        """Continue app startup after setup screen is dismissed."""
        if completed:
            self._app._update_resource_bar()
        self._start_repl()

    def _start_repl(self) -> None:
        """Initialize REPL components after setup flow completes."""
        if self._repl_started:
            return
        self._repl_started = True

        self._setup_logger()

        app = self._app
        app.set_focus(app.editor)
        app.run_worker(app._request_worker, exclusive=False)
        self._start_slopgotchi_timer()
        app._update_resource_bar()

        from tunacode.ui.welcome import show_welcome

        show_welcome(app.chat_container)

    def _setup_logger(self) -> None:
        """Initialize logger output to the app chat container."""
        from tunacode.core.logging import get_logger

        app = self._app
        logger = get_logger()
        logger.set_state_manager(self._state_manager)

        def write_tui(renderable: RenderableType) -> None:
            app.chat_container.write(renderable)

        logger.set_tui_callback(write_tui)

    def _start_slopgotchi_timer(self) -> None:
        """Start periodic slopgotchi updates."""
        from tunacode.ui.slopgotchi import SLOPGOTCHI_AUTO_MOVE_INTERVAL_SECONDS

        app = self._app
        app._slopgotchi_timer = app.set_interval(
            SLOPGOTCHI_AUTO_MOVE_INTERVAL_SECONDS,
            app._update_slopgotchi,
        )

    def _stop_slopgotchi_timer(self) -> None:
        """Stop periodic slopgotchi updates if running."""
        timer = self._app._slopgotchi_timer
        if timer is None:
            return

        timer.stop()
        self._app._slopgotchi_timer = None
