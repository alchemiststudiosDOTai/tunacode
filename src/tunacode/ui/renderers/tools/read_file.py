"""NeXTSTEP-style panel renderer for read_file tool output."""

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

from tunacode.constants import (
    MAX_PANEL_LINE_WIDTH,
    MIN_VIEWPORT_LINES,
    TOOL_VIEWPORT_LINES,
    UI_COLORS,
)

BOX_HORIZONTAL = "\u2500"
SEPARATOR_WIDTH = 52


@dataclass
class ReadFileData:
    """Parsed read_file result for structured display."""

    filepath: str
    filename: str
    content_lines: list[tuple[int, str]]  # (line_number, content)
    total_lines: int
    offset: int
    has_more: bool
    end_message: str


def parse_result(args: dict[str, Any] | None, result: str) -> ReadFileData | None:
    """Extract structured data from read_file output.

    Expected format:
        <file>
        00001| line content
        00002| line content
        ...

        (File has more lines. Use 'offset' to read beyond line N)
        </file>

    Or:
        <file>
        ...
        (End of file - total N lines)
        </file>
    """
    if not result or "<file>" not in result:
        return None

    # Extract content between <file> tags
    file_match = re.search(r"<file>\n(.*?)\n</file>", result, re.DOTALL)
    if not file_match:
        return None

    content = file_match.group(1)
    lines = content.strip().splitlines()

    if not lines:
        return None

    # Parse line-numbered content: "00001| content"
    content_lines: list[tuple[int, str]] = []
    end_message = ""
    total_lines = 0
    has_more = False

    line_pattern = re.compile(r"^(\d+)\|\s?(.*)")

    for line in lines:
        # Check for end message
        if line.startswith("(File has more"):
            has_more = True
            end_message = line
            # Extract total from "Use 'offset' to read beyond line N"
            match = re.search(r"beyond line (\d+)", line)
            if match:
                total_lines = int(match.group(1))
            continue
        if line.startswith("(End of file"):
            end_message = line
            match = re.search(r"total (\d+) lines", line)
            if match:
                total_lines = int(match.group(1))
            continue

        # Parse line content
        match = line_pattern.match(line)
        if match:
            line_num = int(match.group(1))
            line_content = match.group(2)
            content_lines.append((line_num, line_content))

    if not content_lines:
        return None

    args = args or {}
    filepath = args.get("filepath", "unknown")
    offset = args.get("offset", 0)

    # If total_lines not found in message, estimate from content
    if total_lines == 0:
        total_lines = content_lines[-1][0] if content_lines else 0

    return ReadFileData(
        filepath=filepath,
        filename=Path(filepath).name,
        content_lines=content_lines,
        total_lines=total_lines,
        offset=offset,
        has_more=has_more,
        end_message=end_message,
    )


def _truncate_line(line: str) -> str:
    """Truncate a single line if too wide."""
    if len(line) > MAX_PANEL_LINE_WIDTH:
        return line[: MAX_PANEL_LINE_WIDTH - 3] + "..."
    return line


def render_read_file(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render read_file with NeXTSTEP zoned layout.

    Zones:
    - Header: filename + line range
    - Selection context: filepath
    - Primary viewport: line-numbered content
    - Status: total lines, continuation info, duration
    """
    data = parse_result(args, result)
    if not data:
        return None

    # Zone 1: Filename + line range
    header = Text()
    header.append(data.filename, style="bold")

    if data.content_lines:
        start_line = data.content_lines[0][0]
        end_line = data.content_lines[-1][0]
        header.append(f"   lines {start_line}-{end_line}", style="dim")

    # Zone 2: Full filepath
    params = Text()
    params.append("path:", style="dim")
    params.append(f" {data.filepath}", style="dim bold")

    separator = Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")

    # Zone 3: Content viewport
    viewport_lines: list[str] = []
    max_display = TOOL_VIEWPORT_LINES

    for i, (line_num, line_content) in enumerate(data.content_lines):
        if i >= max_display:
            break
        formatted = f"{line_num:>5}| {line_content}"
        viewport_lines.append(_truncate_line(formatted))

    # Pad viewport to minimum height for visual consistency
    while len(viewport_lines) < MIN_VIEWPORT_LINES:
        viewport_lines.append("")

    viewport = Text("\n".join(viewport_lines)) if viewport_lines else Text("(empty file)")

    # Zone 4: Status
    status_items: list[str] = []

    shown = min(len(data.content_lines), max_display)
    if shown < len(data.content_lines):
        status_items.append(f"[{shown}/{len(data.content_lines)} displayed]")

    if data.has_more:
        status_items.append(f"total: {data.total_lines} lines")
        status_items.append("(more available)")
    elif data.total_lines > 0:
        status_items.append(f"total: {data.total_lines} lines")

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
        title=f"[{UI_COLORS['success']}]read_file[/] [done]",
        subtitle=f"[{UI_COLORS['muted']}]{timestamp}[/]",
        border_style=Style(color=UI_COLORS["success"]),
        padding=(0, 1),
        expand=False,
    )
