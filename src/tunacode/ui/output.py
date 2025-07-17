"""Output and display functions for TunaCode UI."""

from prompt_toolkit.application import run_in_terminal
from rich.console import Console
from rich.padding import Padding

from tunacode.configuration.settings import ApplicationSettings
from tunacode.constants import (
    MSG_UPDATE_AVAILABLE,
    MSG_UPDATE_INSTRUCTION,
    MSG_VERSION_DISPLAY,
    UI_COLORS,
    UI_THINKING_MESSAGE,
)
from tunacode.core.state import StateManager
from tunacode.utils.file_utils import DotDict
from tunacode.utils.token_counter import format_token_count

from .constants import SPINNER_TYPE
from .decorators import create_sync_wrapper

console = Console()
colors = DotDict(UI_COLORS)

BANNER = """[bold cyan]
████████╗██╗   ██╗███╗   ██╗ █████╗
╚══██╔══╝██║   ██║████╗  ██║██╔══██╗
   ██║   ██║   ██║██╔██╗ ██║███████║
   ██║   ██║   ██║██║╚██╗██║██╔══██║
   ██║   ╚██████╔╝██║ ╚████║██║  ██║
   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝

 ██████╗ ██████╗ ██████╗ ███████╗  dev
██╔════╝██╔═══██╗██╔══██╗██╔════╝
██║     ██║   ██║██║  ██║█████╗
██║     ██║   ██║██║  ██║██╔══╝
╚██████╗╚██████╔╝██████╔╝███████╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
[/bold cyan]

● Caution: This tool can modify your codebase - always use git branches"""


@create_sync_wrapper
async def print(message, **kwargs) -> None:
    """Print a message to the console."""
    await run_in_terminal(lambda: console.print(message, **kwargs))


async def line() -> None:
    """Print an empty line for spacing."""
    await print("")


async def info(text: str) -> None:
    """Print an informational message."""
    await print(f"[{colors.primary}]●[/{colors.primary}] {text}", style=colors.muted)


async def success(message: str) -> None:
    """Print a success message."""
    await print(f"[{colors.success}]✓[/{colors.success}] {message}")


async def warning(text: str) -> None:
    """Print a warning message."""
    await print(f"[{colors.warning}]⚠[/{colors.warning}] {text}")


async def muted(text: str) -> None:
    """Print muted text."""
    await print(text, style=colors.muted)


async def usage(usage: str) -> None:
    """Print usage information."""
    await print(Padding(usage, (0, 0, 1, 2)), style=colors.muted)


async def version() -> None:
    """Print version information."""
    app_settings = ApplicationSettings()
    await info(MSG_VERSION_DISPLAY.format(version=app_settings.version))


async def banner() -> None:
    """Display the application banner."""
    await run_in_terminal(lambda: console.clear())
    banner_padding = Padding(BANNER, (2, 0, 1, 0))
    await run_in_terminal(lambda: console.print(banner_padding))


async def clear() -> None:
    """Clear the console and display the banner."""
    console.clear()
    await banner()


async def update_available(latest_version: str) -> None:
    """Display update available notification."""
    await warning(MSG_UPDATE_AVAILABLE.format(latest_version=latest_version))
    await muted(MSG_UPDATE_INSTRUCTION)


async def show_update_message(latest_version: str) -> None:
    """Display update available message (alias for update_available)."""
    await update_available(latest_version)


async def spinner(show: bool = True, spinner_obj=None, state_manager: StateManager = None):
    """Manage a spinner display."""
    icon = SPINNER_TYPE
    message = UI_THINKING_MESSAGE

    # Get spinner from state manager if available
    if spinner_obj is None and state_manager:
        spinner_obj = state_manager.session.spinner

    if not spinner_obj:
        spinner_obj = await run_in_terminal(lambda: console.status(message, spinner=icon))
        # Store it back in state manager if available
        if state_manager:
            state_manager.session.spinner = spinner_obj

    if show:
        spinner_obj.start()
    else:
        spinner_obj.stop()

    return spinner_obj


def get_context_window_display(total_tokens: int, max_tokens: int) -> str:
    """
    Create a color-coded display for the context window status.

    Args:
        total_tokens: The current number of tokens in the context.
        max_tokens: The maximum number of tokens for the model.

    Returns:
        A formatted string for display.
    """
    if max_tokens == 0:
        return ""

    percentage = (float(total_tokens) / float(max_tokens)) * 100 if max_tokens else 0
    color = "success"
    if percentage > 80:
        color = "error"
    elif percentage > 50:
        color = "warning"

    return (
        f"[b]Context:[/] [{colors[color]}]"
        f"{format_token_count(total_tokens)}/{format_token_count(max_tokens)} "
        f"({int(percentage)}%)[/]"
    )


# Auto-generated sync version
sync_print = print.sync  # type: ignore
