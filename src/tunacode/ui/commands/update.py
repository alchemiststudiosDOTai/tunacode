"""Update command for checking and installing package upgrades."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp

PACKAGE_NAME = "tunacode-cli"
UPDATE_INSTALL_TIMEOUT_SECONDS = 120


def _get_package_manager_command(package: str) -> tuple[list[str], str] | None:
    """Get package manager command and name.

    Returns:
        tuple(list[str], str) for command and manager name, or None if unavailable.
    """

    import shutil

    uv_path = shutil.which("uv")
    if uv_path:
        return ([uv_path, "pip", "install", "--upgrade", package], "uv")

    pip_path = shutil.which("pip")
    if pip_path:
        return ([pip_path, "install", "--upgrade", package], "pip")

    return None


class UpdateCommand(Command):
    """Check for and install updates to tunacode."""

    name = "update"
    description = "Update tunacode to latest version"
    usage = "/update [check]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        parts = args.split(maxsplit=1) if args else []
        subcommand = parts[0].lower() if parts else "install"

        handler = {
            "check": self._handle_check,
            "install": self._handle_install,
        }.get(subcommand)

        if handler is None:
            app.notify(f"Unknown subcommand: {subcommand}", severity="warning")
            app.notify("Usage: /update [check]")
            return

        await handler(app)

    async def _handle_check(self, app: TextualReplApp) -> None:
        """Check for updates without installing."""
        import asyncio

        from tunacode.core.ui_api.constants import APP_VERSION
        from tunacode.core.ui_api.system_paths import check_for_updates

        app.notify("Checking for updates...")
        has_update, latest_version = await asyncio.to_thread(check_for_updates)

        if not has_update:
            app.notify(f"Already on latest version ({APP_VERSION})")
            return

        app.rich_log.write(f"Current version: {APP_VERSION}")
        app.rich_log.write(f"Latest version:  {latest_version}")
        app.notify(f"Update available: {latest_version}")
        app.rich_log.write("Run /update to upgrade")

    async def _handle_install(self, app: TextualReplApp) -> None:
        """Check for updates and install if available."""
        import asyncio
        import subprocess

        from tunacode.core.ui_api.constants import APP_VERSION
        from tunacode.core.ui_api.system_paths import check_for_updates

        from tunacode.ui.screens.update_confirm import UpdateConfirmScreen

        app.notify("Checking for updates...")
        has_update, latest_version = await asyncio.to_thread(check_for_updates)

        if not has_update:
            app.notify(f"Already on latest version ({APP_VERSION})")
            return

        def on_update_confirmed(confirmed: bool | None) -> None:
            """Handle user's response to update confirmation."""
            if not confirmed:
                app.notify("Update cancelled")
                return

            pkg_cmd_result = _get_package_manager_command(PACKAGE_NAME)
            if not pkg_cmd_result:
                app.notify("No package manager found (uv or pip)", severity="error")
                return

            cmd, pkg_mgr = pkg_cmd_result
            app.notify(f"Installing with {pkg_mgr}...")

            async def install_update() -> None:
                try:
                    result = await asyncio.to_thread(
                        subprocess.run,
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=UPDATE_INSTALL_TIMEOUT_SECONDS,
                    )

                    if result.returncode == 0:
                        app.notify(f"Updated to {latest_version}!")
                        app.rich_log.write("Restart tunacode to use the new version")
                    else:
                        app.notify("Update failed", severity="error")
                        if result.stderr:
                            app.rich_log.write(result.stderr.strip())
                except Exception as e:
                    app.rich_log.write(f"Error: {e}")

            app.run_worker(install_update(), exclusive=False)

        app.push_screen(UpdateConfirmScreen(APP_VERSION, latest_version), on_update_confirmed)
