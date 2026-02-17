"""Welcome screen: logo generation and welcome message."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from rich.console import RenderableType
from rich.text import Text

from tunacode.core.ui_api.constants import APP_NAME, APP_VERSION

from tunacode.ui.logo_assets import LOGO_WELCOME_FILENAME, read_logo_ansi
from tunacode.ui.styles import (
    STYLE_MUTED,
    STYLE_PRIMARY,
    STYLE_WARNING,
)

if TYPE_CHECKING:
    from textual.widget import Widget


class WriteableLog(Protocol):
    """Protocol for widgets that support write() method."""

    def write(self, renderable: RenderableType) -> Widget: ...


WELCOME_TITLE_FORMAT = ">>> {name} v{version}"
SECTION_DIVIDER = "   ──────────────────────────────────────────────\n\n"


def generate_logo() -> Text:
    """Load the pre-rendered logo as rich text."""
    logo_ansi = read_logo_ansi(LOGO_WELCOME_FILENAME)
    return Text.from_ansi(logo_ansi)


def show_welcome(log: WriteableLog) -> None:
    """Display welcome message with logo to the given log widget."""
    try:
        logo = generate_logo()
    except FileNotFoundError as exc:
        log.write(Text(str(exc), style=STYLE_WARNING))
    else:
        log.write(logo)

    welcome_title = WELCOME_TITLE_FORMAT.format(name=APP_NAME, version=APP_VERSION)
    welcome = Text()
    welcome.append("\n")
    welcome.append(f"{welcome_title}\n", style=STYLE_PRIMARY)
    welcome.append("AI coding assistant in your terminal.\n\n", style=STYLE_MUTED)

    # Group 1: Core navigation
    welcome.append("   /help", style=STYLE_PRIMARY)
    welcome.append("       - Show all commands\n")
    welcome.append("   /clear", style=STYLE_PRIMARY)
    welcome.append("      - Clear agent state (messages preserved)\n")
    welcome.append("   /resume", style=STYLE_PRIMARY)
    welcome.append("     - Load saved session\n\n")
    welcome.append(SECTION_DIVIDER, style=STYLE_MUTED)

    # Group 2: Switching
    welcome.append("   /model", style=STYLE_PRIMARY)
    welcome.append("      - Switch model\n")
    welcome.append("   /theme", style=STYLE_PRIMARY)
    welcome.append("      - Switch theme\n\n")
    welcome.append(SECTION_DIVIDER, style=STYLE_MUTED)

    # Group 3: Shell & extras
    welcome.append("   !<cmd>", style=STYLE_PRIMARY)
    welcome.append("      - Run shell commands\n")
    welcome.append("   /thoughts", style=STYLE_PRIMARY)
    welcome.append("   - Toggle model thinking panel\n\n")
    welcome.append(SECTION_DIVIDER, style=STYLE_MUTED)

    # Slopgotchi
    welcome.append("   Your ", style=STYLE_MUTED)
    welcome.append("slopgotchi", style=STYLE_PRIMARY)
    welcome.append(" lives in the context panel (", style=STYLE_MUTED)
    welcome.append("ctrl+e", style=STYLE_PRIMARY)
    welcome.append("). Click it!\n\n", style=STYLE_MUTED)

    log.write(welcome)
