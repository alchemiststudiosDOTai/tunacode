"""Right-side info panel widget for TunaCode REPL.

Provides at-a-glance status information following NeXTSTEP design principles.
Displays: model, token usage, edited files, tool activity, and mode indicators.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

from tunacode.ui.styles import (
    STYLE_ERROR,
    STYLE_MUTED,
    STYLE_PRIMARY,
    STYLE_SUCCESS,
    STYLE_WARNING,
)

# Panel configuration
PANEL_WIDTH = 26
MAX_FILES_SHOWN = 10
MAX_FILENAME_LEN = 18


@dataclass
class FileChange:
    """Tracks a file change with add/remove line counts."""

    filepath: str
    additions: int = 0
    deletions: int = 0


@dataclass
class InfoPanelState:
    """State container for InfoPanel data."""

    model: str = "---"
    tokens: int = 0
    max_tokens: int = 200000
    session_cost: float = 0.0
    edited_files: dict[str, FileChange] = field(default_factory=dict)
    current_tool: str | None = None
    last_tool: str | None = None
    plan_mode: bool = False
    lsp_server: str | None = None


class InfoPanel(Container):
    """Right-side info panel with glanceable status.

    Sections (top to bottom):
    - Model: Current model name
    - Usage: Token usage indicator, remaining %, cost
    - Files: Recently edited files with +/- indicators
    - Tools: Current/last tool execution
    - Mode: Plan mode indicator (if active)
    """

    DEFAULT_CSS = """
    InfoPanel {
        dock: right;
        width: 26;
        height: 100%;
        border-left: solid $border;
        padding: 0 1;
        background: $background;
    }

    InfoPanel .section-header {
        color: $text-muted;
        text-style: bold;
        margin-top: 1;
    }

    InfoPanel .section-content {
        padding-left: 1;
    }

    InfoPanel #panel-model {
        margin-top: 0;
    }

    InfoPanel .file-entry {
        color: $text;
    }

    InfoPanel .mode-indicator {
        color: $warning;
        text-style: bold;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._state = InfoPanelState()

    def compose(self) -> ComposeResult:
        yield Static("MODEL", classes="section-header", id="panel-model-header")
        yield Static("---", id="panel-model", classes="section-content")

        yield Static("USAGE", classes="section-header")
        yield Static("", id="panel-usage", classes="section-content")

        yield Static("FILES", classes="section-header")
        yield Static("", id="panel-files", classes="section-content")

        yield Static("TOOLS", classes="section-header")
        yield Static("", id="panel-tools", classes="section-content")

        yield Static("", id="panel-mode", classes="mode-indicator")

    def on_mount(self) -> None:
        self._refresh_all()

    def update_model(self, model: str) -> None:
        """Update the displayed model name."""
        self._state.model = model
        self._refresh_model()

    def update_usage(
        self,
        *,
        tokens: int | None = None,
        max_tokens: int | None = None,
        session_cost: float | None = None,
    ) -> None:
        """Update token usage and cost display."""
        if tokens is not None:
            self._state.tokens = tokens
        if max_tokens is not None:
            self._state.max_tokens = max_tokens
        if session_cost is not None:
            self._state.session_cost = session_cost
        self._refresh_usage()

    def add_edited_file(self, filepath: str, additions: int = 0, deletions: int = 0) -> None:
        """Track an edited file with change metrics."""
        filename = os.path.basename(filepath)
        if filename in self._state.edited_files:
            existing = self._state.edited_files[filename]
            existing.additions += additions
            existing.deletions += deletions
        else:
            self._state.edited_files[filename] = FileChange(
                filepath=filepath,
                additions=additions,
                deletions=deletions,
            )
        self._refresh_files()

    def update_tool(self, tool_name: str | None, *, running: bool = False) -> None:
        """Update tool status display."""
        if running:
            self._state.current_tool = tool_name
        else:
            self._state.current_tool = None
            if tool_name:
                self._state.last_tool = tool_name
        self._refresh_tools()

    def set_plan_mode(self, enabled: bool) -> None:
        """Update plan mode indicator."""
        self._state.plan_mode = enabled
        self._refresh_mode()

    def set_lsp_server(self, server: str | None) -> None:
        """Update LSP server indicator."""
        self._state.lsp_server = server
        self._refresh_mode()

    def _refresh_all(self) -> None:
        """Refresh all panel sections."""
        self._refresh_model()
        self._refresh_usage()
        self._refresh_files()
        self._refresh_tools()
        self._refresh_mode()

    def _refresh_model(self) -> None:
        """Refresh model display."""
        model_widget = self.query_one("#panel-model", Static)
        # Truncate long model names
        model = self._state.model
        if len(model) > PANEL_WIDTH - 2:
            model = model[: PANEL_WIDTH - 5] + "..."
        model_widget.update(Text(model, style=STYLE_PRIMARY))

    def _refresh_usage(self) -> None:
        """Refresh usage display with token indicator and cost."""
        usage_widget = self.query_one("#panel-usage", Static)

        remaining_pct = self._calculate_remaining_pct()
        circle_char = self._get_circle_char(remaining_pct)
        circle_color = self._get_circle_color(remaining_pct)

        content = Text()
        content.append(circle_char, style=circle_color)
        content.append(f" {remaining_pct:.0f}%", style=circle_color)
        content.append("  ", style=STYLE_MUTED)
        content.append(f"${self._state.session_cost:.2f}", style=STYLE_SUCCESS)

        usage_widget.update(content)

    def _refresh_files(self) -> None:
        """Refresh edited files display."""
        files_widget = self.query_one("#panel-files", Static)
        files = self._state.edited_files

        if not files:
            files_widget.update(Text("-", style=STYLE_MUTED))
            return

        content = Text()
        # Show most recent files first (dict maintains insertion order)
        file_list = list(files.values())[-MAX_FILES_SHOWN:]

        for i, fc in enumerate(file_list):
            if i > 0:
                content.append("\n")

            # Truncate long filenames
            name = os.path.basename(fc.filepath)
            if len(name) > MAX_FILENAME_LEN:
                name = name[: MAX_FILENAME_LEN - 3] + "..."

            content.append(name, style=STYLE_PRIMARY)

            # Show +/- indicators if we have change metrics
            if fc.additions > 0 or fc.deletions > 0:
                content.append(" ", style=STYLE_MUTED)
                if fc.additions > 0:
                    content.append(f"+{fc.additions}", style=STYLE_SUCCESS)
                if fc.deletions > 0:
                    if fc.additions > 0:
                        content.append("/", style=STYLE_MUTED)
                    content.append(f"-{fc.deletions}", style=STYLE_ERROR)

        files_widget.update(content)

    def _refresh_tools(self) -> None:
        """Refresh tools display."""
        tools_widget = self.query_one("#panel-tools", Static)
        content = Text()

        if self._state.current_tool:
            content.append("running: ", style=STYLE_MUTED)
            content.append(self._state.current_tool, style=STYLE_WARNING)
        elif self._state.last_tool:
            content.append("last: ", style=STYLE_MUTED)
            content.append(self._state.last_tool, style=STYLE_SUCCESS)
        else:
            content.append("-", style=STYLE_MUTED)

        tools_widget.update(content)

    def _refresh_mode(self) -> None:
        """Refresh mode indicators."""
        mode_widget = self.query_one("#panel-mode", Static)
        content = Text()

        indicators: list[str] = []
        if self._state.plan_mode:
            indicators.append("PLAN")
        if self._state.lsp_server:
            indicators.append(f"LSP:{self._state.lsp_server}")

        if indicators:
            content.append("\n")
            content.append(" | ".join(indicators), style=STYLE_WARNING)

        mode_widget.update(content)

    def _calculate_remaining_pct(self) -> float:
        """Calculate remaining token percentage."""
        if self._state.max_tokens == 0:
            return 0.0
        raw_pct = (self._state.max_tokens - self._state.tokens) / self._state.max_tokens * 100
        return max(0.0, min(100.0, raw_pct))

    def _get_circle_color(self, remaining_pct: float) -> str:
        """Get color for token usage circle based on remaining percentage."""
        if remaining_pct > 60:
            return STYLE_SUCCESS
        if remaining_pct > 30:
            return STYLE_WARNING
        return STYLE_ERROR

    def _get_circle_char(self, remaining_pct: float) -> str:
        """Get visual circle character based on remaining percentage."""
        if remaining_pct > 87.5:
            return "●"
        if remaining_pct > 62.5:
            return "◕"
        if remaining_pct > 37.5:
            return "◑"
        if remaining_pct > 12.5:
            return "◔"
        return "○"
