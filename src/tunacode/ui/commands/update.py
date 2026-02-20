"""Update command: check PyPI and upgrade if a newer version exists."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp

PACKAGE_NAME = "tunacode-cli"
UPDATE_INSTALL_TIMEOUT_SECONDS = 120


def _is_tool_install() -> bool:
    """Detect whether tunacode is running inside an isolated tool venv.

    Returns True when the install looks like pipx or ``uv tool`` (the
    executable lives under a path that contains a tool-managed venv).
    """
    import sys

    exe = sys.executable
    # pipx venvs:   ~/.local/pipx/venvs/<pkg>/...
    # uv tool:      ~/.local/share/uv/tools/<pkg>/...
    return "/pipx/venvs/" in exe or "/uv/tools/" in exe


def _get_package_manager_command(package: str) -> tuple[list[str], str] | None:
    """Get the correct upgrade command for the user's install method.

    Handles three scenarios:
    1. ``uv tool install`` -> ``uv tool upgrade``
    2. ``pipx install``    -> ``pipx upgrade``
    3. Plain pip/uv pip    -> ``uv pip install --upgrade`` / ``pip install --upgrade``

    Returns:
        tuple(list[str], str) for command and manager name, or None if unavailable.
    """
    import shutil

    if _is_tool_install():
        uv_path = shutil.which("uv")
        if uv_path:
            return ([uv_path, "tool", "upgrade", package], "uv tool")

        pipx_path = shutil.which("pipx")
        if pipx_path:
            return ([pipx_path, "upgrade", package], "pipx")

    uv_path = shutil.which("uv")
    if uv_path:
        return ([uv_path, "pip", "install", "--upgrade", package], "uv pip")

    pip_path = shutil.which("pip")
    if pip_path:
        return ([pip_path, "install", "--upgrade", package], "pip")

    return None


class UpdateCommand(Command):
    """Check for and install updates to tunacode."""

    name = "update"
    description = "Update tunacode to latest version"
    usage = "/update"

    async def execute(self, app: TextualReplApp, _args: str) -> None:
        import asyncio
        import subprocess

        from tunacode.core.ui_api.system_paths import (
            check_for_updates,
            get_installed_version,
        )

        from tunacode.ui.screens.update_confirm import UpdateConfirmScreen

        installed_version = get_installed_version()
        app.rich_log.write("Checking for updates...")

        try:
            has_update, latest_version = await asyncio.to_thread(check_for_updates)
        except RuntimeError as exc:
            app.rich_log.write(f"Update check failed: {exc}")
            return

        if not has_update:
            app.rich_log.write(f"Already on latest version ({installed_version})")
            return

        app.rich_log.write(f"Installed: {installed_version}  ->  Latest: {latest_version}")

        def on_update_confirmed(confirmed: bool | None) -> None:
            """Handle user's response to update confirmation."""
            if not confirmed:
                app.notify("Update cancelled")
                return

            pkg_cmd_result = _get_package_manager_command(PACKAGE_NAME)
            if not pkg_cmd_result:
                app.rich_log.write("No package manager found (uv or pip)")
                return

            cmd, pkg_mgr = pkg_cmd_result
            app.rich_log.write(f"Installing with {pkg_mgr}...")

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
                        msg = f"Updated to {latest_version}! Restart tunacode to use it."
                        app.rich_log.write(msg)
                    else:
                        app.rich_log.write(f"Update failed: {result.stderr.strip()}")
                except Exception as e:
                    app.rich_log.write(f"Error: {e}")

            app.run_worker(install_update(), exclusive=False)

        app.push_screen(UpdateConfirmScreen(installed_version, latest_version), on_update_confirmed)
