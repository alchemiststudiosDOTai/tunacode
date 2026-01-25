"""Summary viewer modal screen for TunaCode."""

from __future__ import annotations

from rich.markdown import Markdown
from rich.panel import Panel
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

# Modal layout constants
MODAL_WIDTH_PERCENT = 80
MODAL_HEIGHT_PERCENT = 80
MODAL_PADDING_VERTICAL = 1
MODAL_PADDING_HORIZONTAL = 2


class SummaryViewerScreen(ModalScreen[None]):
    """Modal screen to display conversation summary."""

    CSS = f"""
    SummaryViewerScreen {{
        align: center middle;
    }}

    #summary-container {{
        width: {MODAL_WIDTH_PERCENT}%;
        height: {MODAL_HEIGHT_PERCENT}%;
        border: solid $primary;
        background: $surface;
        padding: {MODAL_PADDING_VERTICAL} {MODAL_PADDING_HORIZONTAL};
    }}

    #summary-scroll {{
        width: 100%;
        height: 100%;
    }}
    """

    BINDINGS = [
        Binding("ctrl+o", "dismiss", "Close", show=False),
        Binding("escape", "dismiss", "Close", show=False),
    ]

    def __init__(self, summary_content: str) -> None:
        super().__init__()
        self._summary_content = summary_content

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="summary-container"):
            yield Static(
                Panel(
                    Markdown(self._summary_content),
                    title="Conversation Summary",
                    subtitle="ctrl+o or escape to close",
                    border_style="dim",
                ),
                id="summary-content",
            )

    def action_dismiss(self) -> None:
        self.dismiss(None)
