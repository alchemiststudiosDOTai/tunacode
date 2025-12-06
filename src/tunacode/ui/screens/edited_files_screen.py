"""Edited files list modal screen for TunaCode."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option


class EditedFilesScreen(Screen[None]):
    """Modal screen displaying all edited files."""

    CSS = """
    EditedFilesScreen {
        align: center middle;
    }

    #files-container {
        width: 60;
        height: auto;
        max-height: 24;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #files-title {
        text-style: bold;
        color: $accent;
        text-align: center;
        margin-bottom: 1;
    }

    #files-list {
        height: auto;
        max-height: 18;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Close"),
    ]

    def __init__(self, edited_files: list[str]) -> None:
        super().__init__()
        self._files = edited_files

    def compose(self) -> ComposeResult:
        with Vertical(id="files-container"):
            count = len(self._files)
            title = f"Edited Files ({count})" if count else "No Edited Files"
            yield Static(title, id="files-title")

            options = [Option(f) for f in self._files]
            yield OptionList(*options, id="files-list")

    def action_cancel(self) -> None:
        self.dismiss(None)
