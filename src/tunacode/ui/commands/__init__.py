"""Command system for TunaCode REPL."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp

from tunacode.ui.styles import STYLE_PRIMARY


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


class ModelCommand(Command):
    name = "model"
    description = "Open model picker or switch directly"
    usage = "/model [provider:model-name]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from tunacode.utils.config.user_configuration import save_config

        if args:
            model_name = args.strip()
            app.state_manager.session.current_model = model_name
            app.state_manager.session.user_config["default_model"] = model_name
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
                if full_model is not None:
                    app.state_manager.session.current_model = full_model
                    app.state_manager.session.user_config["default_model"] = full_model
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
        app.notify("Plan mode not yet implemented", severity="warning")


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


COMMANDS: dict[str, Command] = {
    "help": HelpCommand(),
    "clear": ClearCommand(),
    "yolo": YoloCommand(),
    "model": ModelCommand(),
    "branch": BranchCommand(),
    "plan": PlanCommand(),
    "theme": ThemeCommand(),
}


async def handle_command(app: TextualReplApp, text: str) -> bool:
    """Handle a command if text starts with / or !.

    Returns True if command was handled, False otherwise.
    """
    if text.startswith("!"):
        await run_shell_command(app, text[1:])
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


async def run_shell_command(app: TextualReplApp, cmd: str) -> None:
    """Run a shell command and display output."""
    import asyncio
    import subprocess

    if not cmd.strip():
        app.notify("Usage: !<command>", severity="warning")
        return

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            shell=True,  # noqa: S602 - intentional shell command from user
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout or result.stderr
        if output:
            app.rich_log.write(output.rstrip())
        if result.returncode != 0:
            app.notify(f"Exit code: {result.returncode}", severity="warning")
    except subprocess.TimeoutExpired:
        app.notify("Command timed out", severity="error")
    except Exception as e:
        app.rich_log.write(f"Error: {e}")
