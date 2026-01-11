"""Welcome screen: logo generation and welcome message."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rich.text import Text
from textual.widgets import RichLog

from tunacode.ui.styles import (
    STYLE_HEADING,
    STYLE_MUTED,
    STYLE_PRIMARY,
)


def generate_logo() -> Text | None:
    """Generate logo using chafa if available."""
    if not shutil.which("chafa"):
        return None

    # Find logo image - check package location first, then relative path
    logo_paths = [
        Path(__file__).parent.parent.parent.parent / "docs" / "images" / "logo.jpeg",
        Path.cwd() / "docs" / "images" / "logo.jpeg",
    ]

    logo_path = None
    for path in logo_paths:
        if path.exists():
            logo_path = path
            break

    if not logo_path:
        return None

    try:
        result = subprocess.run(
            [
                "chafa",
                "-f", "symbols",
                "-c", "full",
                "--size=24x12",
                "--bg=#1a1a1a",
                str(logo_path),
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout:
            return Text.from_ansi(result.stdout)
    except (subprocess.TimeoutExpired, OSError):
        pass

    return None


def show_welcome(rich_log: RichLog) -> None:
    """Display welcome message with logo to the given RichLog."""
    # Try to show logo
    logo = generate_logo()
    if logo:
        rich_log.write(logo)

    welcome = Text()
    welcome.append("\n")
    welcome.append("Welcome to TunaCode\n", style=STYLE_HEADING)
    welcome.append("AI coding assistant in your terminal.\n\n", style=STYLE_MUTED)

    # Group 1: Core navigation
    welcome.append("   /help", style=STYLE_PRIMARY)
    welcome.append("       - Show all commands\n")
    welcome.append("   /clear", style=STYLE_PRIMARY)
    welcome.append("      - Clear conversation\n")
    welcome.append("   /resume", style=STYLE_PRIMARY)
    welcome.append("     - Load saved session\n\n")
    welcome.append("   ──────────────────────────────────────────────\n\n", style=STYLE_MUTED)

    # Group 2: Mode toggles
    welcome.append("   /yolo", style=STYLE_PRIMARY)
    welcome.append("       - Toggle auto-confirm\n")
    welcome.append("   /plan", style=STYLE_PRIMARY)
    welcome.append("       - Toggle planning mode\n\n")
    welcome.append("   ──────────────────────────────────────────────\n\n", style=STYLE_MUTED)

    # Group 3: Switching
    welcome.append("   /model", style=STYLE_PRIMARY)
    welcome.append("      - Switch model\n")
    welcome.append("   /theme", style=STYLE_PRIMARY)
    welcome.append("      - Switch theme\n\n")
    welcome.append("   ──────────────────────────────────────────────\n\n", style=STYLE_MUTED)

    # Group 4: Git/shell
    welcome.append("   /branch", style=STYLE_PRIMARY)
    welcome.append("     - Create git branch\n")
    welcome.append("   !<cmd>", style=STYLE_PRIMARY)
    welcome.append("      - Run shell commands\n\n")
    rich_log.write(welcome)
