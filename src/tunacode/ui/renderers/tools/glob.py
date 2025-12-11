"""NeXTSTEP-style panel renderer for glob tool output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from tunacode.constants import MAX_PANEL_LINE_WIDTH, MAX_PANEL_LINES, UI_COLORS

BOX_HORIZONTAL = "\u2500"
SEPARATOR_WIDTH = 52


@dataclass
class GlobData:
    """Parsed glob result for structured display."""

    pattern: str
    file_count: int
    files: list[str]
    source: str  # "index" or "filesystem"
    is_truncated: bool
    recursive: bool
    include_hidden: bool
    sort_by: str


def parse_result(args: dict[str, Any] | None, result: str) -> GlobData | None:
    """Extract structured data from glob output.

    Expected format:
        [source:index]
        Found N file(s) matching pattern: <pattern>

        /path/to/file1.py
        /path/to/file2.py
        (truncated at N)
    """
    if not result:
        return None

    lines = result.strip().splitlines()
    if not lines:
        return None

    # Extract source marker
    source = "filesystem"
    start_idx = 0
    if lines[0].startswith("[source:"):
        marker = lines[0]
        source = marker[8:-1]  # Extract between "[source:" and "]"
        start_idx = 1

    # Parse header
    if start_idx >= len(lines):
        return None

    header_line = lines[start_idx]
    header_match = re.match(r"Found (\d+) files? matching pattern: (.+)", header_line)
    if not header_match:
        # Check for "No files found" case
        if "No files found" in header_line:
            return None
        return None

    file_count = int(header_match.group(1))
    pattern = header_match.group(2).strip()

    # Parse file list
    files: list[str] = []
    is_truncated = False

    for line in lines[start_idx + 1 :]:
        line = line.strip()
        if not line:
            continue
        if line.startswith("(truncated"):
            is_truncated = True
            continue
        # File paths
        if line.startswith("/") or line.startswith("./") or "/" in line:
            files.append(line)

    args = args or {}
    return GlobData(
        pattern=pattern,
        file_count=file_count,
        files=files,
        source=source,
        is_truncated=is_truncated,
        recursive=args.get("recursive", True),
        include_hidden=args.get("include_hidden", False),
        sort_by=args.get("sort_by", "modified"),
    )


def _truncate_path(path: str) -> str:
    """Truncate a path if too wide, keeping filename visible."""
    if len(path) <= MAX_PANEL_LINE_WIDTH:
        return path

    p = Path(path)
    filename = p.name
    max_dir_len = MAX_PANEL_LINE_WIDTH - len(filename) - 4  # ".../"

    if max_dir_len <= 0:
        return "..." + filename[-(MAX_PANEL_LINE_WIDTH - 3) :]

    dir_part = str(p.parent)
    if len(dir_part) > max_dir_len:
        dir_part = "..." + dir_part[-(max_dir_len - 3) :]

    return f"{dir_part}/{filename}"


def render_glob(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render glob with NeXTSTEP zoned layout.

    Zones:
    - Header: pattern + file count
    - Selection context: recursive, hidden, sort parameters
    - Primary viewport: file list
    - Status: source (indexed/scanned), truncation, duration
    """
    data = parse_result(args, result)
    if not data:
        return None

    # Zone 1: Pattern + counts
    header = Text()
    header.append(f'"{data.pattern}"', style="bold")
    file_word = "file" if data.file_count == 1 else "files"
    header.append(f"   {data.file_count} {file_word}", style="dim")

    # Zone 2: Parameters
    recursive_val = "on" if data.recursive else "off"
    hidden_val = "on" if data.include_hidden else "off"
    params = Text()
    params.append("recursive:", style="dim")
    params.append(f" {recursive_val}", style="dim bold")
    params.append("  hidden:", style="dim")
    params.append(f" {hidden_val}", style="dim bold")
    params.append("  sort:", style="dim")
    params.append(f" {data.sort_by}", style="dim bold")

    separator = Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")

    # Zone 3: File list viewport
    viewport_lines: list[str] = []
    max_display = MAX_PANEL_LINES - 2

    for i, filepath in enumerate(data.files):
        if i >= max_display:
            break
        viewport_lines.append(_truncate_path(filepath))

    viewport = Text("\n".join(viewport_lines)) if viewport_lines else Text("(no files)")

    # Zone 4: Status
    status_items: list[str] = []

    # Source indicator (cache hit/miss)
    if data.source == "index":
        status_items.append("indexed")
    else:
        status_items.append("scanned")

    if data.is_truncated or len(data.files) < data.file_count:
        shown = min(len(data.files), max_display)
        status_items.append(f"[{shown}/{data.file_count} shown]")

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

    # Use accent color for index hits, muted for filesystem scans
    border_color = UI_COLORS["success"] if data.source == "index" else UI_COLORS["success"]

    return Panel(
        content,
        title=f"[{UI_COLORS['success']}]glob[/] [done]",
        subtitle=f"[{UI_COLORS['muted']}]{timestamp}[/]",
        border_style=Style(color=border_color),
        padding=(0, 1),
        expand=False,
    )
