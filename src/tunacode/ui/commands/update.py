"""Update command: check PyPI and upgrade if a newer version exists."""

from __future__ import annotations

import shutil
import sys
from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp

PACKAGE_NAME = "tunacode-cli"
UPDATE_INSTALL_TIMEOUT_SECONDS = 120
UV_TOOL_NOT_INSTALLED_ERROR_MARKERS = (
    "failed to upgrade",
    "is not installed",
    "uv tool install",
)


def _is_tool_install() -> bool:
    """Detect whether tunacode is running inside an isolated tool venv.

    Returns True when the install looks like pipx or ``uv tool`` (the
    executable lives under a path that contains a tool-managed venv).
    """
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


def _should_retry_uv_tool_with_active_python(stderr: str) -> bool:
    """Return True when uv tool cannot locate the currently running install.

    uv's exact stderr format is not a stable API, so match a small set of
    lower-cased markers instead of a single full substring.
    """
    normalized_stderr = stderr.strip().casefold()
    return all(marker in normalized_stderr for marker in UV_TOOL_NOT_INSTALLED_ERROR_MARKERS)


def _get_active_python_upgrade_command(package: str) -> tuple[list[str], str] | None:
    """Build a direct upgrade command against the active interpreter."""
    uv_path = shutil.which("uv")
    if uv_path:
        return (
            [uv_path, "pip", "install", "--python", sys.executable, "--upgrade", package],
            "uv pip",
        )

    return None


async def _run_upgrade_command(
    app: TextualReplApp,
    cmd: list[str],
    pkg_mgr: str,
    package: str,
) -> tuple[int, str]:
    """Run the selected upgrade command and retry against the active interpreter when needed."""
    import asyncio
    import subprocess

    result = await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        text=True,
        timeout=UPDATE_INSTALL_TIMEOUT_SECONDS,
    )

    if result.returncode == 0 or pkg_mgr != "uv tool":
        return result.returncode, result.stderr.strip()

    fallback_cmd_result = _get_active_python_upgrade_command(package)
    if not fallback_cmd_result or not _should_retry_uv_tool_with_active_python(result.stderr):
        return result.returncode, result.stderr.strip()

    fallback_cmd, fallback_mgr = fallback_cmd_result
    app.chat_container.write(
        "uv tool could not locate this install; "
        f"retrying with {fallback_mgr} against the active Python..."
    )
    fallback_result = await asyncio.to_thread(
        subprocess.run,
        fallback_cmd,
        capture_output=True,
        text=True,
        timeout=UPDATE_INSTALL_TIMEOUT_SECONDS,
    )
    return fallback_result.returncode, fallback_result.stderr.strip()


class UpdateCommand(Command):
    """Check for and install updates to tunacode."""

    name = "update"
    description = "Update tunacode to latest version"
    usage = "/update"

    async def execute(self, app: TextualReplApp, _args: str) -> None:
        import asyncio

        from tunacode.configuration.paths import _get_installed_version as get_installed_version
        from tunacode.configuration.paths import check_for_updates

        from tunacode.ui.screens.update_confirm import UpdateConfirmScreen

        installed_version = get_installed_version()
        app.chat_container.write("Checking for updates...")

        try:
            has_update, latest_version = await asyncio.to_thread(check_for_updates)
        except RuntimeError as exc:
            app.chat_container.write(f"Update check failed: {exc}")
            return

        if not has_update:
            app.chat_container.write(f"Already on latest version ({installed_version})")
            return

        app.chat_container.write(f"Installed: {installed_version}  ->  Latest: {latest_version}")

        def on_update_confirmed(confirmed: bool | None) -> None:
            """Handle user's response to update confirmation."""
            if not confirmed:
                app.notify("Update cancelled")
                return

            pkg_cmd_result = _get_package_manager_command(PACKAGE_NAME)
            if not pkg_cmd_result:
                app.chat_container.write("No package manager found (uv or pip)")
                return

            cmd, pkg_mgr = pkg_cmd_result
            app.chat_container.write(f"Installing with {pkg_mgr}...")

            async def install_update() -> None:
                try:
                    returncode, stderr = await _run_upgrade_command(
                        app,
                        cmd,
                        pkg_mgr,
                        PACKAGE_NAME,
                    )

                    if returncode == 0:
                        msg = f"Updated to {latest_version}! Restart tunacode to use it."
                        app.chat_container.write(msg)
                    else:
                        app.chat_container.write(f"Update failed: {stderr}")
                except Exception as e:
                    app.chat_container.write(f"Error: {e}")

            app.run_worker(install_update(), exclusive=False)

        app.push_screen(UpdateConfirmScreen(installed_version, latest_version), on_update_confirmed)
