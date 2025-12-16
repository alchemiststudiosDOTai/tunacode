"""Status bar widget for TunaCode REPL."""

from __future__ import annotations

import os
import subprocess

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

# Maximum length for operation text in status bar
MAX_STATUS_OPERATION_LEN = 25


class StatusBar(Horizontal):
    """Bottom status bar - 3 zones."""

    def __init__(self) -> None:
        super().__init__()
        self._edited_files: set[str] = set()
        self._location_text: str = ""

    def compose(self) -> ComposeResult:
        yield Static("main ● ~/proj", id="status-left")
        yield Static("edited: -", id="status-mid")
        yield Static("last: -", id="status-right")

    def on_mount(self) -> None:
        self._refresh_location()

    def _refresh_location(self) -> None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            branch = result.stdout.strip() or "main"
        except Exception:
            branch = "main"

        dirname = os.path.basename(os.getcwd()) or "~"
        self._location_text = f"{branch} ● {dirname}"
        self.query_one("#status-left", Static).update(self._location_text)

    def update_last_action(self, tool_name: str) -> None:
        self.query_one("#status-right", Static).update(f"last: {tool_name}")

    def update_running_action(self, tool_name: str) -> None:
        self.query_one("#status-right", Static).update(f"running: {tool_name}")

    def update_subagent_progress(
        self, subagent: str, operation: str, current: int, _total: int
    ) -> None:
        """Update status with subagent progress.

        Shows format: running: research [3] grep pattern...
        """
        # Truncate operation to fit status bar
        if len(operation) > MAX_STATUS_OPERATION_LEN:
            operation = operation[: MAX_STATUS_OPERATION_LEN - 3] + "..."

        # Format: running: subagent [current/?] operation
        # Use ? for total since we don't know upfront how many operations
        progress_text = f"running: {subagent} [{current}] {operation}"
        self.query_one("#status-right", Static).update(progress_text)

    def add_edited_file(self, filepath: str) -> None:
        """Track an edited file and update display."""
        filename = os.path.basename(filepath)
        self._edited_files.add(filename)
        self._update_edited_display()

    def _update_edited_display(self) -> None:
        """Update mid zone with edited files list."""
        files = sorted(self._edited_files)
        if not files:
            text = "edited: -"
        elif len(files) <= 3:
            text = f"edited: {', '.join(files)}"
        else:
            shown = ", ".join(files[:2])
            text = f"edited: {shown} +{len(files) - 2}"
        self.query_one("#status-mid", Static).update(text)

    def set_mode(self, mode: str | None) -> None:
        """Show mode indicator in status bar."""
        left = self.query_one("#status-left", Static)
        if mode:
            left.add_class("mode-active")
            left.update(f"[{mode}] {self._location_text}")
        else:
            left.remove_class("mode-active")
            left.update(self._location_text)
