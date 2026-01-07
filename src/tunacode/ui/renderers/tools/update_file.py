"""NeXTSTEP-style panel renderer for update_file tool output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from tunacode.constants import (
    MAX_PANEL_LINE_WIDTH,
    MIN_VIEWPORT_LINES,
    TOOL_PANEL_WIDTH,
    TOOL_VIEWPORT_LINES,
)
from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    tool_renderer,
)


@dataclass
class UpdateFileData:
    """Parsed update_file result for structured display."""

    filepath: str
    filename: str
    message: str
    diff_content: str
    additions: int
    deletions: int
    hunks: int
    diagnostics_block: str | None = None


class UpdateFileRenderer(BaseToolRenderer[UpdateFileData]):
    """Renderer for update_file tool output with optional diagnostics zone."""

    def parse_result(self, args: dict[str, Any] | None, result: str) -> UpdateFileData | None:
        """Extract structured data from update_file output.

        Expected format:
            File 'path/to/file.py' updated successfully.

            --- a/path/to/file.py
            +++ b/path/to/file.py
            @@ -10,5 +10,7 @@
            ...diff content...

            <file_diagnostics>
            Error (line 10): type mismatch
            </file_diagnostics>
        """
        if not result:
            return None

        # Extract diagnostics block before parsing diff
        from tunacode.ui.renderers.tools.diagnostics import extract_diagnostics_from_result

        result_clean, diagnostics_block = extract_diagnostics_from_result(result)

        # Split message from diff
        if "\n--- a/" not in result_clean:
            return None

        parts = result_clean.split("\n--- a/", 1)
        message = parts[0].strip()
        diff_content = "--- a/" + parts[1]

        # Extract filepath from diff header
        filepath_match = re.search(r"--- a/(.+)", diff_content)
        if not filepath_match:
            # Try from args
            args = args or {}
            filepath = args.get("filepath", "unknown")
        else:
            filepath = filepath_match.group(1).strip()

        # Count additions and deletions
        additions = 0
        deletions = 0
        hunks = 0

        for line in diff_content.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
            elif line.startswith("@@"):
                hunks += 1

        return UpdateFileData(
            filepath=filepath,
            filename=Path(filepath).name,
            message=message,
            diff_content=diff_content,
            additions=additions,
            deletions=deletions,
            hunks=hunks,
            diagnostics_block=diagnostics_block,
        )

    def build_header(self, data: UpdateFileData, duration_ms: float | None) -> Text:
        """Zone 1: Filename + change stats."""
        header = Text()
        header.append(data.filename, style="bold")
        header.append("   ", style="")
        header.append(f"+{data.additions}", style="green")
        header.append(" ", style="")
        header.append(f"-{data.deletions}", style="red")
        return header

    def build_params(self, data: UpdateFileData) -> Text:
        """Zone 2: Full filepath."""
        params = Text()
        params.append("path:", style="dim")
        params.append(f" {data.filepath}", style="dim bold")
        return params

    def build_viewport(self, data: UpdateFileData) -> RenderableType:
        """Zone 3: Diff viewport with syntax highlighting."""
        # Truncate diff
        truncated_diff, shown, total = self._truncate_diff(data.diff_content)

        # Pad viewport to minimum height
        diff_lines = truncated_diff.split("\n")
        while len(diff_lines) < MIN_VIEWPORT_LINES:
            diff_lines.append("")
        truncated_diff = "\n".join(diff_lines)

        return Syntax(truncated_diff, "diff", theme="monokai", word_wrap=True)

    def _truncate_line_width(self, line: str, max_line_width: int) -> str:
        if len(line) <= max_line_width:
            return line
        return line[:max_line_width] + "..."

    def _truncate_diff(self, diff: str) -> tuple[str, int, int]:
        """Truncate diff content, return (truncated, shown, total)."""
        lines = diff.splitlines()
        total = len(lines)
        max_content = TOOL_VIEWPORT_LINES
        max_line_width = MAX_PANEL_LINE_WIDTH

        capped_lines = [
            self._truncate_line_width(line, max_line_width) for line in lines[:max_content]
        ]

        if total <= max_content:
            return "\n".join(capped_lines), total, total
        return "\n".join(capped_lines), max_content, total

    def build_status(self, data: UpdateFileData, duration_ms: float | None) -> Text:
        """Zone 4: Status with hunks, truncation info, timing."""

        status_items: list[str] = []

        hunk_word = "hunk" if data.hunks == 1 else "hunks"
        status_items.append(f"{data.hunks} {hunk_word}")

        _, shown, total = self._truncate_diff(data.diff_content)
        if shown < total:
            status_items.append(f"[{shown}/{total} lines]")

        if duration_ms is not None:
            status_items.append(f"{duration_ms:.0f}ms")

        return Text("  ".join(status_items), style="dim") if status_items else Text("")

    def render(
        self,
        args: dict[str, Any] | None,
        result: str,
        duration_ms: float | None = None,
    ) -> RenderableType | None:
        """Render update_file with NeXTSTEP zoned layout plus optional diagnostics.

        Zones:
        - Zone 1: Header (filename + change stats)
        - Zone 2: Params (filepath)
        - Zone 3: Viewport (syntax-highlighted diff)
        - Zone 4: Status (hunks, truncation info, timing)
        - Zone 5: Diagnostics (if present)
        """
        data = self.parse_result(args, result)
        if data is None:
            return None

        # Build zones
        header = self.build_header(data, duration_ms)
        params = self.build_params(data)
        viewport = self.build_viewport(data)
        status = self.build_status(data, duration_ms)
        separator = self.build_separator()

        content_parts: list[RenderableType] = [
            header,
            Text("\n"),
        ]

        if params is not None:
            content_parts.extend([params, Text("\n")])

        content_parts.extend(
            [
                separator,
                Text("\n"),
                viewport,
                Text("\n"),
                separator,
                Text("\n"),
                status,
            ]
        )

        # Add diagnostics zone if present
        if data.diagnostics_block:
            from tunacode.ui.renderers.tools.diagnostics import (
                parse_diagnostics_block,
                render_diagnostics_inline,
            )

            diag_data = parse_diagnostics_block(data.diagnostics_block)
            if diag_data and diag_data.items:
                content_parts.extend(
                    [
                        Text("\n"),
                        separator,
                        Text("\n"),
                        render_diagnostics_inline(diag_data),
                    ]
                )

        content = Group(*content_parts)

        timestamp = datetime.now().strftime("%H:%M:%S")
        border_color = self.get_border_color(data)
        status_text = self.get_status_text(data)

        return Panel(
            content,
            title=f"[{border_color}]{self.config.tool_name}[/] [{status_text}]",
            subtitle=f"[{self.config.muted_color}]{timestamp}[/]",
            border_style=Style(color=border_color),
            padding=(0, 1),
            expand=True,
            width=TOOL_PANEL_WIDTH,
        )


# Module-level renderer instance
_renderer = UpdateFileRenderer(RendererConfig(tool_name="update_file"))


@tool_renderer("update_file")
def render_update_file(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render update_file with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms)
