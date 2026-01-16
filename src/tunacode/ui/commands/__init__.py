"""Command system for TunaCode REPL."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp

from tunacode.configuration.settings import ApplicationSettings
from tunacode.ui.styles import STYLE_PRIMARY

# Update command constants
PACKAGE_NAME = "tunacode-cli"
UPDATE_INSTALL_TIMEOUT_SECONDS = 120


def _get_package_manager_command(package: str) -> tuple[list[str], str] | None:
    """Get package manager command and name.

    Returns:
        Tuple of (command_list, manager_name) or None if no manager found.
    """
    import shutil

    uv_path = shutil.which("uv")
    if uv_path:
        return ([uv_path, "pip", "install", "--upgrade", package], "uv")

    pip_path = shutil.which("pip")
    if pip_path:
        return ([pip_path, "install", "--upgrade", package], "pip")

    return None


class Command(ABC):
    """Base class for REPL commands."""

    name: str
    description: str
    usage: str = ""

    @abstractmethod
    async def execute(self, app: TextualReplApp, args: str) -> None:
        """Execute the command."""
        pass


class HelpCommand(Command):
    name = "help"
    description = "Show available commands"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from rich.table import Table

        table = Table(title="Commands", show_header=True)
        table.add_column("Command", style=STYLE_PRIMARY)
        table.add_column("Description")

        for name, cmd in COMMANDS.items():
            table.add_row(f"/{name}", cmd.description)

        table.add_row("!<cmd>", "Run shell command")
        table.add_row("exit", "Exit TunaCode")

        app.rich_log.write(table)


class ClearCommand(Command):
    name = "clear"
    description = "Clear conversation history"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        app.rich_log.clear()
        app.state_manager.session.messages = []
        app.state_manager.session.total_tokens = 0
        app._update_resource_bar()
        app.notify("Cleared conversation history")


class YoloCommand(Command):
    name = "yolo"
    description = "Toggle auto-confirm for tool executions"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        app.state_manager.session.yolo = not app.state_manager.session.yolo
        status = "ON" if app.state_manager.session.yolo else "OFF"
        app.notify(f"YOLO mode: {status}")


class DebugCommand(Command):
    name = "debug"
    description = "Toggle debug logging to screen"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from tunacode.core.logging import get_logger

        session = app.state_manager.session
        session.debug_mode = not session.debug_mode

        logger = get_logger()
        logger.set_debug_mode(session.debug_mode)

        status = "ON" if session.debug_mode else "OFF"
        app.notify(f"Debug mode: {status}")

        if session.debug_mode:
            app.rich_log.write(
                "[dim]Debug logging enabled. "
                "Logs also written to ~/.local/share/tunacode/logs/tunacode.log[/dim]"
            )
            logger.info("Debug mode enabled")


def _validate_provider_api_key_with_notification(
    model_string: str,
    user_config: dict,
    app: TextualReplApp,
    show_config_path: bool = False,
) -> bool:
    """Validate API key for provider and notify user if missing.

    Returns True if valid (or no provider in string), False otherwise.
    """
    from tunacode.configuration.models import validate_provider_api_key

    if ":" not in model_string:
        return True

    provider_id = model_string.split(":")[0]
    is_valid, env_var = validate_provider_api_key(provider_id, user_config)

    if not is_valid:
        app.notify(f"Missing API key: {env_var}", severity="error")
        msg = f"[yellow]Set {env_var} in config for {provider_id}[/yellow]"
        if show_config_path:
            config_path = ApplicationSettings().paths.config_file
            msg += f"\n[dim]Config: {config_path}[/dim]"
        app.rich_log.write(msg)

    return is_valid


class ModelCommand(Command):
    name = "model"
    description = "Open model picker or switch directly"
    usage = "/model [provider:model-name]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from tunacode.configuration.models import (
            get_model_context_window,
            load_models_registry,
        )
        from tunacode.utils.config.user_configuration import save_config

        if args:
            load_models_registry()
            model_name = args.strip()

            if not _validate_provider_api_key_with_notification(
                model_name,
                app.state_manager.session.user_config,
                app,
                show_config_path=True,
            ):
                return

            app.state_manager.session.current_model = model_name
            app.state_manager.session.user_config["default_model"] = model_name
            app.state_manager.session.max_tokens = get_model_context_window(model_name)
            save_config(app.state_manager)
            app._update_resource_bar()
            app.notify(f"Model: {model_name}")
        else:
            from tunacode.ui.screens.model_picker import (
                ModelPickerScreen,
                ProviderPickerScreen,
            )

            current_model = app.state_manager.session.current_model

            def on_model_selected(full_model: str | None) -> None:
                if full_model is None:
                    return

                if not _validate_provider_api_key_with_notification(
                    full_model,
                    app.state_manager.session.user_config,
                    app,
                    show_config_path=False,
                ):
                    return

                app.state_manager.session.current_model = full_model
                app.state_manager.session.user_config["default_model"] = full_model
                app.state_manager.session.max_tokens = get_model_context_window(full_model)
                save_config(app.state_manager)
                app._update_resource_bar()
                app.notify(f"Model: {full_model}")

            def on_provider_selected(provider_id: str | None) -> None:
                if provider_id is not None:
                    app.push_screen(
                        ModelPickerScreen(provider_id, current_model),
                        on_model_selected,
                    )

            app.push_screen(
                ProviderPickerScreen(current_model),
                on_provider_selected,
            )


class BranchCommand(Command):
    name = "branch"
    description = "Create and switch to a new git branch"
    usage = "/branch <name>"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        import subprocess

        if not args:
            app.notify("Usage: /branch <name>", severity="warning")
            return

        branch_name = args.strip()
        try:
            result = subprocess.run(
                ["git", "checkout", "-b", branch_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                app.notify(f"Created branch: {branch_name}")
                app.status_bar._refresh_location()
            else:
                app.rich_log.write(f"Error: {result.stderr.strip()}")
        except Exception as e:
            app.rich_log.write(f"Error: {e}")


class PlanCommand(Command):
    name = "plan"
    description = "Toggle read-only planning mode"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        session = app.state_manager.session
        session.plan_mode = not session.plan_mode

        if session.plan_mode:
            # Set up the approval callback for the present_plan tool
            async def plan_approval_callback(plan_content: str) -> tuple[bool, str]:
                return await app.request_plan_approval(plan_content)

            session.plan_approval_callback = plan_approval_callback

            # NeXTSTEP: Modes must be visually apparent at all times
            app.status_bar.set_mode("PLAN")
            app.notify("Plan mode ON - write/bash tools blocked")
            app.rich_log.write(
                "[bold]Plan mode active[/bold]\n"
                "Blocked: write_file, update_file, bash\n"
                "Use read-only tools to gather context, then call present_plan."
            )
        else:
            # Clear the callback
            session.plan_approval_callback = None

            # NeXTSTEP: Clear mode indicator
            app.status_bar.set_mode(None)
            app.notify("Plan mode OFF - all tools available")


class ThemeCommand(Command):
    name = "theme"
    description = "Open theme picker or switch directly"
    usage = "/theme [name]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from tunacode.utils.config.user_configuration import save_config

        if args:
            theme_name = args.strip()
            if theme_name not in app.available_themes:
                app.notify(f"Unknown theme: {theme_name}", severity="error")
                return

            app.theme = theme_name
            app.state_manager.session.user_config.setdefault("settings", {})["theme"] = theme_name
            save_config(app.state_manager)
            app.notify(f"Theme: {theme_name}")
        else:
            from tunacode.ui.screens.theme_picker import ThemePickerScreen

            def on_dismiss(selected: str | None) -> None:
                if selected is not None:
                    config = app.state_manager.session.user_config
                    config.setdefault("settings", {})["theme"] = selected
                    save_config(app.state_manager)
                    app.notify(f"Theme: {selected}")

            app.push_screen(
                ThemePickerScreen(app.available_themes, app.theme),
                on_dismiss,
            )


class ResumeCommand(Command):
    name = "resume"
    description = "Resume a previous session"
    usage = "/resume [load <id>|delete <id>]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from tunacode.ui.screens import SessionPickerScreen
        from tunacode.utils.system.paths import delete_session_file

        parts = args.split(maxsplit=1) if args else []
        subcommand = parts[0].lower() if parts else ""

        # No args or "list" -> open picker
        if subcommand in ("", "list"):
            sessions = app.state_manager.list_sessions()
            if not sessions:
                app.notify("No saved sessions found")
                return

            current_session_id = app.state_manager.session.session_id

            def on_session_selected(session_id: str | None) -> None:
                if not session_id:
                    return
                self._load_session(app, session_id, sessions)

            app.push_screen(
                SessionPickerScreen(sessions, current_session_id),
                on_session_selected,
            )

        elif subcommand == "load":
            if len(parts) < 2:
                app.notify("Usage: /resume load <session-id>", severity="warning")
                return

            session_id_prefix = parts[1].strip()
            sessions = app.state_manager.list_sessions()

            matching = [s for s in sessions if s["session_id"].startswith(session_id_prefix)]
            if not matching:
                app.notify(f"No session found matching: {session_id_prefix}", severity="error")
                return
            if len(matching) > 1:
                app.notify("Multiple sessions match, be more specific", severity="warning")
                return

            self._load_session(app, matching[0]["session_id"], sessions)

        elif subcommand == "delete":
            if len(parts) < 2:
                app.notify("Usage: /resume delete <session-id>", severity="warning")
                return

            session_id_prefix = parts[1].strip()
            sessions = app.state_manager.list_sessions()

            matching = [s for s in sessions if s["session_id"].startswith(session_id_prefix)]
            if not matching:
                app.notify(f"No session found matching: {session_id_prefix}", severity="error")
                return
            if len(matching) > 1:
                app.notify("Multiple sessions match, be more specific", severity="warning")
                return

            target_session = matching[0]
            if target_session["session_id"] == app.state_manager.session.session_id:
                app.notify("Cannot delete current session", severity="error")
                return

            project_id = app.state_manager.session.project_id
            if delete_session_file(project_id, target_session["session_id"]):
                app.notify(f"Deleted session {target_session['session_id'][:8]}")
            else:
                app.notify("Failed to delete session", severity="error")

        else:
            app.notify(f"Unknown subcommand: {subcommand}", severity="warning")

    def _load_session(self, app: TextualReplApp, session_id: str, sessions: list[dict]) -> None:
        """Load a session by ID."""
        from rich.text import Text

        target = next((s for s in sessions if s["session_id"] == session_id), None)
        if not target:
            app.notify("Session not found", severity="error")
            return

        app.state_manager.save_session()

        if app.state_manager.load_session(session_id):
            app.rich_log.clear()
            app._replay_session_messages()
            app._update_resource_bar()

            loaded_msg = Text()
            loaded_msg.append(
                f"Loaded session {session_id[:8]} ({target['message_count']} messages)\n",
                style="green",
            )
            app.rich_log.write(loaded_msg)
            app.notify("Session loaded")
        else:
            app.notify("Failed to load session", severity="error")


class UpdateCommand(Command):
    name = "update"
    description = "Check for or install updates"
    usage = "/update [check|install]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        import asyncio
        import subprocess

        from tunacode.constants import APP_VERSION
        from tunacode.utils.system.paths import check_for_updates

        parts = args.split(maxsplit=1) if args else []
        subcommand = parts[0].lower() if parts else "check"

        if subcommand == "check":
            app.notify("Checking for updates...")
            has_update, latest_version = await asyncio.to_thread(check_for_updates)

            if has_update:
                app.rich_log.write(f"Current version: {APP_VERSION}")
                app.rich_log.write(f"Latest version:  {latest_version}")
                app.notify(f"Update available: {latest_version}")
                app.rich_log.write("Run /update install to upgrade")
            else:
                app.notify(f"Already on latest version ({APP_VERSION})")

        elif subcommand == "install":
            from tunacode.ui.screens.update_confirm import UpdateConfirmScreen

            app.notify("Checking for updates...")
            has_update, latest_version = await asyncio.to_thread(check_for_updates)

            if not has_update:
                app.notify(f"Already on latest version ({APP_VERSION})")
                return

            confirmed = await app.push_screen_wait(UpdateConfirmScreen(APP_VERSION, latest_version))

            if not confirmed:
                app.notify("Update cancelled")
                return

            pkg_cmd_result = _get_package_manager_command(PACKAGE_NAME)
            if not pkg_cmd_result:
                app.notify("No package manager found (uv or pip)", severity="error")
                return

            cmd, pkg_mgr = pkg_cmd_result
            app.notify(f"Installing with {pkg_mgr}...")

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

        else:
            app.notify(f"Unknown subcommand: {subcommand}", severity="warning")
            app.notify("Usage: /update [check|install]")


COMMANDS: dict[str, Command] = {
    "help": HelpCommand(),
    "clear": ClearCommand(),
    "yolo": YoloCommand(),
    "debug": DebugCommand(),
    "model": ModelCommand(),
    "branch": BranchCommand(),
    "plan": PlanCommand(),
    "theme": ThemeCommand(),
    "resume": ResumeCommand(),
    "update": UpdateCommand(),
}


async def handle_command(app: TextualReplApp, text: str) -> bool:
    """Handle a command if text starts with / or !.

    Returns True if command was handled, False otherwise.
    """
    if text.startswith("!"):
        app.start_shell_command(text[1:])
        return True

    if text.startswith("/"):
        parts = text[1:].split(maxsplit=1)
        cmd_name = parts[0].lower() if parts else ""
        cmd_args = parts[1] if len(parts) > 1 else ""

        if cmd_name in COMMANDS:
            await COMMANDS[cmd_name].execute(app, cmd_args)
            return True
        else:
            app.notify(f"Unknown command: /{cmd_name}", severity="warning")
            return True

    if text.lower() == "exit":
        app.exit()
        return True

    return False
