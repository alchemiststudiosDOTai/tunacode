"""NeXTSTEP-style panel renderer for list_dir tool output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from tunacode.constants import (
    MAX_PANEL_LINE_WIDTH,
    MIN_VIEWPORT_LINES,
    TOOL_PANEL_WIDTH,
    TOOL_VIEWPORT_LINES,
    UI_COLORS,
)
from tunacode.tools.list_dir import IGNORE_PATTERNS_COUNT

BOX_HORIZONTAL = "─"
SEPARATOR_WIDTH = 52


@dataclass
class ListDirData:
    """Parsed list_dir result for structured display."""

    directory: str
    tree_content: str
    file_count: int
    dir_count: int
    is_truncated: bool
    max_files: int
    show_hidden: bool
    ignore_count: int


def parse_result(args: dict[str, Any] | None, result: str) -> ListDirData | None:
    """Extract structured data from list_dir output.

    New format:
        45 files  12 dirs
        dirname/
        ├── subdir/
        │   └── file.txt
        └── other.txt
    """
    if not result:
        return None

    lines = result.strip().splitlines()
    if len(lines) < 2:
        return None

    # First line is summary: "45 files  12 dirs" or "0 files  0 dirs"
    summary_line = lines[0]
    summary_match = re.match(r"(\d+)\s+files\s+(\d+)\s+dirs(?:\s+\(truncated\))?", summary_line)

    if not summary_match:
        return None

    file_count = int(summary_match.group(1))
    dir_count = int(summary_match.group(2))
    is_truncated = "(truncated)" in summary_line

    # Second line is directory name
    directory = lines[1].rstrip("/")

    # Rest is tree content
    tree_content = "\n".join(lines[1:])

    args = args or {}
    max_files = args.get("max_files", 100)
    show_hidden = args.get("show_hidden", False)
    ignore_list = args.get("ignore", [])
    ignore_count = (
        IGNORE_PATTERNS_COUNT + len(ignore_list) if ignore_list else IGNORE_PATTERNS_COUNT
    )

    return ListDirData(
        directory=directory,
        tree_content=tree_content,
        file_count=file_count,
        dir_count=dir_count,
        is_truncated=is_truncated,
        max_files=max_files,
        show_hidden=show_hidden,
        ignore_count=ignore_count,
    )


def _truncate_line(line: str) -> str:
    """Truncate a single line if too wide."""
    if len(line) > MAX_PANEL_LINE_WIDTH:
        return line[: MAX_PANEL_LINE_WIDTH - 3] + "..."
    return line


def _truncate_tree(content: str) -> tuple[str, int, int]:
    """Truncate tree content, return (truncated, shown, total)."""
    lines = content.splitlines()
    total = len(lines)

    if total <= TOOL_VIEWPORT_LINES:
        return "\n".join(_truncate_line(ln) for ln in lines), total, total

    truncated = [_truncate_line(ln) for ln in lines[:TOOL_VIEWPORT_LINES]]
    return "\n".join(truncated), TOOL_VIEWPORT_LINES, total


def render_list_dir(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render list_dir with NeXTSTEP zoned layout.

    Zones:
    - Header: directory path + summary counts
    - Selection context: hidden/max/ignore parameters
    - Primary viewport: tree content with connectors
    - Status: truncation info, duration
    """
    data = parse_result(args, result)
    if not data:
        return None

    # Zone 1: Directory + counts
    header = Text()
    header.append(data.directory, style="bold")
    header.append(f"   {data.file_count} files  {data.dir_count} dirs", style="dim")

    # Zone 2: Parameters
    hidden_val = "on" if data.show_hidden else "off"
    params = Text()
    params.append("hidden:", style="dim")
    params.append(f" {hidden_val}", style="dim bold")
    params.append("  max:", style="dim")
    params.append(f" {data.max_files}", style="dim bold")
    params.append("  ignore:", style="dim")
    params.append(f" {data.ignore_count}", style="dim bold")

    separator = Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")

    # Zone 3: Tree viewport (skip first line which is dirname)
    tree_lines = data.tree_content.splitlines()[1:]  # skip dirname, already in header
    tree_only = "\n".join(tree_lines) if tree_lines else "(empty)"
    truncated_tree, shown, total = _truncate_tree(tree_only)

    # Pad viewport to minimum height for visual consistency
    tree_line_list = truncated_tree.split("\n")
    while len(tree_line_list) < MIN_VIEWPORT_LINES:
        tree_line_list.append("")
    truncated_tree = "\n".join(tree_line_list)

    viewport = Text(truncated_tree)

    # Zone 4: Status
    status_items: list[str] = []
    if data.is_truncated:
        status_items.append("(truncated)")
    if shown < total:
        status_items.append(f"[{shown}/{total} lines]")
    if duration_ms is not None:
        status_items.append(f"{duration_ms:.0f}ms")

    status = Text("  ".join(status_items), style="dim") if status_items else Text("")

    # Compose
    content = Group(
        header,
        Text("\n"),
        params,
        Text("\n"),
        separator,
        Text("\n"),
        viewport,
        Text("\n"),
        separator,
        Text("\n"),
        status,
    )

    timestamp = datetime.now().strftime("%H:%M:%S")

    return Panel(
        content,
        title=f"[{UI_COLORS['success']}]list_dir[/] [done]",
        subtitle=f"[{UI_COLORS['muted']}]{timestamp}[/]",
        border_style=Style(color=UI_COLORS["success"]),
        padding=(0, 1),
        expand=True,
        width=TOOL_PANEL_WIDTH,
    )
