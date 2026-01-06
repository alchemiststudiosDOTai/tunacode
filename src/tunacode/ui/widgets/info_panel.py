"""Right-side info panel widget for TunaCode REPL.

Provides at-a-glance status information following NeXTSTEP design principles.
All session info consolidated in one zone: branch, model, usage, LSP, files.
"""

from __future__ import annotations

import os
import subprocess
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

    branch: str = "main"
    project: str = "~"
    model: str = "---"
    tokens: int = 0
    max_tokens: int = 200000
    session_cost: float = 0.0
    lsp_server: str | None = None
    edited_files: dict[str, FileChange] = field(default_factory=dict)
    plan_mode: bool = False


class InfoPanel(Container):
    """Right-side info panel with glanceable status.

    Sections (top to bottom):
    - Branch: Git branch + project name
    - Model: Current model name
    - Usage: Token usage indicator, remaining %, cost
    - LSP: Language server status
    - Files: Recently edited files
    """

    DEFAULT_CSS = """
    InfoPanel {
        dock: right;
        width: 26;
        height: 100%;
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

    InfoPanel #panel-branch-header {
        margin-top: 0;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._state = InfoPanelState()

    def compose(self) -> ComposeResult:
        yield Static("BRANCH", classes="section-header", id="panel-branch-header")
        yield Static("", id="panel-branch", classes="section-content")

        yield Static("MODEL", classes="section-header")
        yield Static("---", id="panel-model", classes="section-content")

        yield Static("USAGE", classes="section-header")
        yield Static("", id="panel-usage", classes="section-content")

        yield Static("LSP", classes="section-header")
        yield Static("", id="panel-lsp", classes="section-content")

        yield Static("FILES", classes="section-header")
        yield Static("", id="panel-files", classes="section-content")

    def on_mount(self) -> None:
        self._refresh_branch()
        self._refresh_all()

    def refresh_branch(self) -> None:
        """Refresh git branch and project info."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            self._state.branch = result.stdout.strip() or "main"
        except Exception:
            self._state.branch = "main"

        self._state.project = os.path.basename(os.getcwd()) or "~"
        self._refresh_branch()

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

    def update_tool(self, tool_name: str | None, *, _running: bool = False) -> None:
        """Update tool status (no-op, kept for interface compatibility)."""
        _ = tool_name  # Interface compatibility

    def set_plan_mode(self, enabled: bool) -> None:
        """Update plan mode indicator."""
        self._state.plan_mode = enabled
        self._refresh_branch()

    def set_lsp_server(self, server: str | None) -> None:
        """Update LSP server indicator."""
        self._state.lsp_server = server
        self._refresh_lsp()

    def refresh_lsp_status(self, user_config: dict | None) -> None:
        """Check LSP configuration and update indicator."""
        if user_config is None:
            self.set_lsp_server(None)
            return

        from pathlib import Path

        from tunacode.lsp.servers import get_server_command

        settings = user_config.get("settings", {})
        lsp_config = settings.get("lsp", {})
        is_enabled = lsp_config.get("enabled", False)

        if not is_enabled:
            self.set_lsp_server(None)
            return

        command = get_server_command(Path("test.py"))
        if command:
            binary = command[0]
            name_map = {
                "ruff": "ruff",
                "pyright-langserver": "pyright",
                "pylsp": "pylsp",
                "typescript-language-server": "tsserver",
                "gopls": "gopls",
                "rust-analyzer": "rust-analyzer",
            }
            self.set_lsp_server(name_map.get(binary, binary))
        else:
            self.set_lsp_server(None)

    def _refresh_all(self) -> None:
        """Refresh all panel sections."""
        self._refresh_branch()
        self._refresh_model()
        self._refresh_usage()
        self._refresh_lsp()
        self._refresh_files()

    def _refresh_branch(self) -> None:
        """Refresh branch and project display."""
        widget = self.query_one("#panel-branch", Static)
        content = Text()

        if self._state.plan_mode:
            content.append("[PLAN] ", style=STYLE_WARNING)

        content.append(self._state.branch, style=STYLE_PRIMARY)
        content.append(" ", style=STYLE_MUTED)
        content.append(self._state.project, style=STYLE_MUTED)

        widget.update(content)

    def _refresh_model(self) -> None:
        """Refresh model display."""
        widget = self.query_one("#panel-model", Static)
        model = self._state.model
        if len(model) > PANEL_WIDTH - 2:
            model = model[: PANEL_WIDTH - 5] + "..."
        widget.update(Text(model, style=STYLE_PRIMARY))

    def _refresh_usage(self) -> None:
        """Refresh usage display with token indicator and cost."""
        widget = self.query_one("#panel-usage", Static)

        remaining_pct = self._calculate_remaining_pct()
        circle_char = self._get_circle_char(remaining_pct)
        circle_color = self._get_circle_color(remaining_pct)

        content = Text()
        content.append(circle_char, style=circle_color)
        content.append(f" {remaining_pct:.0f}%", style=circle_color)
        content.append("  ", style=STYLE_MUTED)
        content.append(f"${self._state.session_cost:.2f}", style=STYLE_SUCCESS)

        widget.update(content)

    def _refresh_lsp(self) -> None:
        """Refresh LSP status display."""
        widget = self.query_one("#panel-lsp", Static)

        if self._state.lsp_server:
            content = Text(self._state.lsp_server, style=STYLE_SUCCESS)
        else:
            content = Text("-", style=STYLE_MUTED)

        widget.update(content)

    def _refresh_files(self) -> None:
        """Refresh edited files display."""
        widget = self.query_one("#panel-files", Static)
        files = self._state.edited_files

        if not files:
            widget.update(Text("-", style=STYLE_MUTED))
            return

        content = Text()
        file_list = list(files.values())[-MAX_FILES_SHOWN:]

        for i, fc in enumerate(file_list):
            if i > 0:
                content.append("\n")

            name = os.path.basename(fc.filepath)
            if len(name) > MAX_FILENAME_LEN:
                name = name[: MAX_FILENAME_LEN - 3] + "..."

            content.append(name, style=STYLE_PRIMARY)

            if fc.additions > 0 or fc.deletions > 0:
                content.append(" ", style=STYLE_MUTED)
                if fc.additions > 0:
                    content.append(f"+{fc.additions}", style=STYLE_SUCCESS)
                if fc.deletions > 0:
                    if fc.additions > 0:
                        content.append("/", style=STYLE_MUTED)
                    content.append(f"-{fc.deletions}", style=STYLE_ERROR)

        widget.update(content)

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
