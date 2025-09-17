"""System-level commands for TunaCode CLI."""

import os
import shutil
import subprocess
import sys
from typing import List

from ....types import CommandContext
from ....ui import console as ui
from ..base import CommandCategory, CommandSpec, SimpleCommand


class HelpCommand(SimpleCommand):
    """Show help information."""

    spec = CommandSpec(
        name="help",
        aliases=["/help"],
        description="Show help information",
        category=CommandCategory.SYSTEM,
    )

    def __init__(self, command_registry=None):
        self._command_registry = command_registry

    async def execute(self, args: List[str], context: CommandContext) -> None:
        await ui.help(self._command_registry)


class ClearCommand(SimpleCommand):
    """Clear screen and message history."""

    spec = CommandSpec(
        name="clear",
        aliases=["/clear"],
        description="Clear the screen and message history",
        category=CommandCategory.NAVIGATION,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        # Patch any orphaned tool calls before clearing
        from tunacode.core.agents import patch_tool_messages

        patch_tool_messages("Conversation cleared", context.state_manager)

        await ui.clear()
        context.state_manager.session.messages = []
        context.state_manager.session.files_in_context.clear()
        await ui.success("Message history and file context cleared")


class RefreshConfigCommand(SimpleCommand):
    """Refresh configuration from defaults."""

    spec = CommandSpec(
        name="refresh",
        aliases=["/refresh"],
        description="Refresh configuration from defaults (useful after updates)",
        category=CommandCategory.SYSTEM,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        from tunacode.configuration.defaults import DEFAULT_USER_CONFIG

        # Update current session config with latest defaults
        for key, value in DEFAULT_USER_CONFIG.items():
            if key not in context.state_manager.session.user_config:
                context.state_manager.session.user_config[key] = value
            elif isinstance(value, dict):
                # Merge dict values, preserving user overrides
                for subkey, subvalue in value.items():
                    if subkey not in context.state_manager.session.user_config[key]:
                        context.state_manager.session.user_config[key][subkey] = subvalue

        # Show updated max_iterations
        max_iterations = context.state_manager.session.user_config.get("settings", {}).get(
            "max_iterations", 20
        )
        await ui.success(f"Configuration refreshed - max iterations: {max_iterations}")


class UpdateCommand(SimpleCommand):
    """Update TunaCode to the latest version."""

    spec = CommandSpec(
        name="update",
        aliases=["/update"],
        description="Update TunaCode to the latest version",
        category=CommandCategory.SYSTEM,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        await ui.info("Checking for TunaCode updates...")

        # Detect installation method
        installation_method = None

        # Check if installed via pipx
        if shutil.which("pipx"):
            try:
                result = subprocess.run(
                    ["pipx", "list"], capture_output=True, text=True, timeout=10
                )
                pipx_installed = "tunacode" in result.stdout.lower()
                if pipx_installed:
                    installation_method = "pipx"
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                pass

        # Check if installed via venv (from install script)
        if not installation_method:
            venv_dir = os.path.expanduser("~/.tunacode-venv")
            venv_tunacode = os.path.join(venv_dir, "bin", "tunacode")
            venv_python = os.path.join(venv_dir, "bin", "python")

            if os.path.exists(venv_tunacode) and os.path.exists(venv_python):
                # Try UV first if available (UV-created venvs don't have pip module)
                if shutil.which("uv"):
                    try:
                        result = subprocess.run(
                            ["uv", "pip", "show", "--python", venv_python, "tunacode-cli"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if result.returncode == 0:
                            installation_method = "venv"
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                        pass

                # Fall back to python -m pip for pip-created venvs
                if not installation_method:
                    try:
                        result = subprocess.run(
                            [venv_python, "-m", "pip", "show", "tunacode-cli"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if result.returncode == 0:
                            installation_method = "venv"
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                        pass

        # Check if installed via uv tool
        if not installation_method:
            if shutil.which("uv"):
                try:
                    result = subprocess.run(
                        ["uv", "tool", "list"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0 and "tunacode-cli" in result.stdout.lower():
                        installation_method = "uv_tool"
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    pass

        # Check if installed via pip
        if not installation_method:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "show", "tunacode-cli"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    installation_method = "pip"
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                pass

        if not installation_method:
            await ui.error("Could not detect TunaCode installation method")
            await ui.muted("Manual update options:")
            await ui.muted("  pipx:    pipx upgrade tunacode")
            await ui.muted("  pip:     pip install --upgrade tunacode-cli")
            await ui.muted("  uv tool: uv tool upgrade tunacode-cli")
            await ui.muted(
                "  venv:    uv pip install --python ~/.tunacode-venv/bin/python --upgrade tunacode-cli"
            )
            return

        # Perform update based on detected method
        try:
            if installation_method == "pipx":
                await ui.info("Updating via pipx...")
                result = subprocess.run(
                    ["pipx", "upgrade", "tunacode"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            elif installation_method == "venv":
                venv_dir = os.path.expanduser("~/.tunacode-venv")
                venv_python = os.path.join(venv_dir, "bin", "python")

                # Check if uv is available (same logic as install script)
                if shutil.which("uv"):
                    await ui.info("Updating via UV in venv...")
                    result = subprocess.run(
                        [
                            "uv",
                            "pip",
                            "install",
                            "--python",
                            venv_python,
                            "--upgrade",
                            "tunacode-cli",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                else:
                    await ui.info("Updating via pip in venv...")
                    result = subprocess.run(
                        [venv_python, "-m", "pip", "install", "--upgrade", "tunacode-cli"],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
            elif installation_method == "uv_tool":
                await ui.info("Updating via UV tool...")
                result = subprocess.run(
                    ["uv", "tool", "upgrade", "tunacode-cli"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            else:  # pip
                await ui.info("Updating via pip...")
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--upgrade",
                        "tunacode-cli",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

            if result.returncode == 0:
                await ui.success("TunaCode updated successfully!")
                await ui.muted("Restart TunaCode to use the new version")

                # Show update output if available
                if result.stdout.strip():
                    output_lines = result.stdout.strip().split("\n")
                    for line in output_lines[-5:]:  # Show last 5 lines
                        if line.strip():
                            await ui.muted(f"  {line}")
            else:
                await ui.error("Update failed")
                if result.stderr:
                    await ui.muted(f"Error: {result.stderr.strip()}")

        except subprocess.TimeoutExpired:
            await ui.error("Update timed out")
        except subprocess.CalledProcessError as e:
            await ui.error(f"Update failed: {e}")
        except FileNotFoundError:
            await ui.error(f"Could not find {installation_method} executable")


class StreamingCommand(SimpleCommand):
    """Toggle streaming display on/off."""

    spec = CommandSpec(
        name="streaming",
        aliases=["/streaming"],
        description="Toggle streaming display on/off",
        category=CommandCategory.SYSTEM,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        current_setting = context.state_manager.session.user_config.get("settings", {}).get(
            "enable_streaming", True
        )

        if args and args[0].lower() in ["on", "true", "1", "enable", "enabled"]:
            new_setting = True
        elif args and args[0].lower() in ["off", "false", "0", "disable", "disabled"]:
            new_setting = False
        else:
            # Toggle current setting
            new_setting = not current_setting

        # Update the configuration
        if "settings" not in context.state_manager.session.user_config:
            context.state_manager.session.user_config["settings"] = {}
        context.state_manager.session.user_config["settings"]["enable_streaming"] = new_setting

        status = "enabled" if new_setting else "disabled"
        await ui.success(f"Streaming display {status}")

        if new_setting:
            await ui.muted(
                "Responses will be displayed progressively as they are generated (default)"
            )
        else:
            await ui.muted("Responses will be displayed all at once after completion")
