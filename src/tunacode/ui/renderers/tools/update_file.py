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

from tunacode.constants import MAX_PANEL_LINE_WIDTH, TOOL_VIEWPORT_LINES, UI_COLORS

BOX_HORIZONTAL = "\u2500"
SEPARATOR_WIDTH = 52
LINE_TRUNCATION_SUFFIX: str = "..."


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


def parse_result(args: dict[str, Any] | None, result: str) -> UpdateFileData | None:
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


def _truncate_line_width(line: str, max_line_width: int) -> str:
    if len(line) <= max_line_width:
        return line
    line_prefix = line[:max_line_width]
    return f"{line_prefix}{LINE_TRUNCATION_SUFFIX}"


def _truncate_diff(diff: str) -> tuple[str, int, int]:
    """Truncate diff content, return (truncated, shown, total)."""
    lines = diff.splitlines()
    total = len(lines)
    max_content = TOOL_VIEWPORT_LINES
    max_line_width = MAX_PANEL_LINE_WIDTH

    capped_lines = [_truncate_line_width(line, max_line_width) for line in lines[:max_content]]

    if total <= max_content:
        return "\n".join(capped_lines), total, total
    return "\n".join(capped_lines), max_content, total


def render_update_file(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render update_file with NeXTSTEP zoned layout.

    Zones:
    - Header: filename + change summary
    - Selection context: full filepath
    - Primary viewport: syntax-highlighted diff
    - Status: hunks, truncation info, duration
    """
    data = parse_result(args, result)
    if not data:
        return None

    # Zone 1: Filename + change stats
    header = Text()
    header.append(data.filename, style="bold")
    header.append("   ", style="")
    header.append(f"+{data.additions}", style="green")
    header.append(" ", style="")
    header.append(f"-{data.deletions}", style="red")

    # Zone 2: Full filepath
    params = Text()
    params.append("path:", style="dim")
    params.append(f" {data.filepath}", style="dim bold")

    separator = Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")

    # Zone 3: Diff viewport with syntax highlighting
    truncated_diff, shown, total = _truncate_diff(data.diff_content)
    diff_syntax = Syntax(truncated_diff, "diff", theme="monokai", word_wrap=True)

    # Zone 4: Status
    status_items: list[str] = []

    hunk_word = "hunk" if data.hunks == 1 else "hunks"
    status_items.append(f"{data.hunks} {hunk_word}")

    if shown < total:
        status_items.append(f"[{shown}/{total} lines]")

    if duration_ms is not None:
        status_items.append(f"{duration_ms:.0f}ms")

    status = Text("  ".join(status_items), style="dim") if status_items else Text("")

    # Zone 5: Diagnostics (if present)
    diagnostics_content: RenderableType | None = None
    if data.diagnostics_block:
        from tunacode.ui.renderers.tools.diagnostics import (
            parse_diagnostics_block,
            render_diagnostics_inline,
        )

        diag_data = parse_diagnostics_block(data.diagnostics_block)
        if diag_data and diag_data.items:
            diagnostics_content = render_diagnostics_inline(diag_data)

    # Compose
    content_parts: list[RenderableType] = [
        header,
        Text("\n"),
        params,
        Text("\n"),
        separator,
        Text("\n"),
        diff_syntax,
        Text("\n"),
        separator,
        Text("\n"),
        status,
    ]

    # Add diagnostics zone if present
    if diagnostics_content:
        content_parts.extend(
            [
                Text("\n"),
                separator,
                Text("\n"),
                diagnostics_content,
            ]
        )

    content = Group(*content_parts)

    timestamp = datetime.now().strftime("%H:%M:%S")

    return Panel(
        content,
        title=f"[{UI_COLORS['success']}]update_file[/] [done]",
        subtitle=f"[{UI_COLORS['muted']}]{timestamp}[/]",
        border_style=Style(color=UI_COLORS["success"]),
        padding=(0, 1),
        expand=False,
    )
