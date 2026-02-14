"""Theme command for selecting and setting UI themes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


class ThemeCommand(Command):
    """Open the theme picker or switch themes by name."""

    name = "theme"
    description = "Open theme picker or switch directly"
    usage = "/theme [name]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from tunacode.core.ui_api.user_configuration import save_config

        supported_themes = app.supported_themes

        if args:
            theme_name = args.strip()
            if theme_name not in supported_themes:
                app.notify(f"Unknown theme: {theme_name}", severity="error")
                return

            app.theme = theme_name
            app.state_manager.session.user_config.setdefault("settings", {})["theme"] = theme_name
            save_config(app.state_manager)
            app.notify(f"Theme: {theme_name}")
            return

        from tunacode.ui.screens.theme_picker import ThemePickerScreen

        def on_dismiss(selected: str | None) -> None:
            if selected is None:
                return

            config = app.state_manager.session.user_config
            config.setdefault("settings", {})["theme"] = selected
            save_config(app.state_manager)
            app.notify(f"Theme: {selected}")

        app.push_screen(
            ThemePickerScreen(supported_themes, app.theme),
            on_dismiss,
        )
