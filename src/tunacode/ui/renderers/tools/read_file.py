"""Slim NeXTSTEP-style panel renderer for read_file tool output.

Dream mockup style:
─ read_file ──────────────────────────── 150 lines
  ↳ src/tunacode/ui/app.py

  1 from __future__ import annotations
  2 import asyncio
  3 ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import RenderableType
from rich.text import Text

from tunacode.constants import MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES
from tunacode.ui.renderers.tools.base import tool_renderer, truncate_line
from tunacode.ui.renderers.tools.slim_base import slim_footer, slim_panel
from tunacode.ui.renderers.tools.syntax_utils import syntax_or_text


@dataclass
class ReadFileData:
    """Parsed read_file result for structured display."""

    filepath: str
    filename: str
    content_lines: list[tuple[int, str]]
    total_lines: int
    offset: int
    has_more: bool


def parse_read_file_result(
    args: dict[str, Any] | None, result: str
) -> ReadFileData | None:
    """Extract structured data from read_file output."""
    if not result or "<file>" not in result:
        return None

    file_match = re.search(r"<file>\n(.*?)\n</file>", result, re.DOTALL)
    if not file_match:
        return None

    content = file_match.group(1)
    lines = content.strip().splitlines()

    if not lines:
        return None

    content_lines: list[tuple[int, str]] = []
    total_lines = 0
    has_more = False

    line_pattern = re.compile(r"^(\d+)\|\s?(.*)")

    for line in lines:
        if line.startswith("(File has more"):
            has_more = True
            match = re.search(r"beyond line (\d+)", line)
            if match:
                total_lines = int(match.group(1))
            continue
        if line.startswith("(End of file"):
            match = re.search(r"total (\d+) lines", line)
            if match:
                total_lines = int(match.group(1))
            continue

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

    if total_lines == 0:
        total_lines = content_lines[-1][0] if content_lines else 0

    return ReadFileData(
        filepath=filepath,
        filename=Path(filepath).name,
        content_lines=content_lines,
        total_lines=total_lines,
        offset=offset,
        has_more=has_more,
    )


@tool_renderer("read_file")
def render_read_file(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render read_file with slim NeXTSTEP panel style.

    Dream mockup format:
    ─ read_file ──────────────────────── 150 lines
      ↳ src/tunacode/ui/app.py

      1 from __future__ import annotations
      2 import asyncio
    """
    data = parse_read_file_result(args, result)
    if data is None:
        return None

    # Build stats
    stats = f"{data.total_lines} lines"

    # Build viewport with syntax highlighting
    if not data.content_lines:
        viewport = Text("(empty file)", style="dim italic")
    else:
        max_display = TOOL_VIEWPORT_LINES
        content_only: list[str] = []

        for i, (_line_num, line_content) in enumerate(data.content_lines):
            if i >= max_display:
                break
            truncated = truncate_line(line_content, max_width=80)
            content_only.append(truncated)

        while len(content_only) < MIN_VIEWPORT_LINES:
            content_only.append("")

        code_content = "\n".join(content_only)
        start_line = data.content_lines[0][0] if data.content_lines else 1

        viewport = syntax_or_text(
            code_content,
            filepath=data.filepath,
            line_numbers=True,
            start_line=start_line,
        )

    # Footer
    shown = min(len(data.content_lines), TOOL_VIEWPORT_LINES)
    footer = slim_footer(shown, len(data.content_lines))

    return slim_panel(
        name="read_file",
        content=viewport,
        stats=stats,
        subtitle=data.filepath,
        footer=footer if str(footer) else None,
    )
