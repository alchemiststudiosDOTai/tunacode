"""Theme picker modal screen for TunaCode."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from textual.theme import Theme


class ThemePickerScreen(Screen[str | None]):
    """Modal screen for theme selection with live preview."""

    CSS = """
    ThemePickerScreen {
        align: center middle;
    }

    #theme-container {
        width: 40;
        height: auto;
        max-height: 20;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #theme-title {
        text-style: bold;
        color: $accent;
        text-align: center;
        margin-bottom: 1;
    }

    #theme-list {
        height: auto;
        max-height: 14;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        themes: dict[str, Theme],
        current_theme: str,
    ) -> None:
        super().__init__()
        self._themes = themes
        self._current_theme = current_theme
        self._original_theme = current_theme

    def compose(self) -> ComposeResult:
        options = []
        highlight_index = 0

        for i, (name, theme) in enumerate(sorted(self._themes.items())):
            label = f"{name} ({'Dark' if theme.dark else 'Light'})"
            options.append(Option(label, id=name))
            if name == self._current_theme:
                highlight_index = i

        with Vertical(id="theme-container"):
            yield Static("Select Theme", id="theme-title")
            option_list = OptionList(*options, id="theme-list")
            option_list.highlighted = highlight_index
            yield option_list

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Live preview: change theme as user navigates."""
        if event.option and event.option.id:
            self.app.theme = str(event.option.id)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Confirm selection and dismiss."""
        if event.option and event.option.id:
            self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        """Cancel and revert to original theme."""
        self.app.theme = self._original_theme
        self.dismiss(None)
