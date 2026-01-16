"""Slim NeXTSTEP-style panel renderer for write_file tool output.

Dream mockup style:
─ write_file ─────────────────────────── 25 lines
  ↳ src/tunacode/ui/new_module.py

  1 from __future__ import annotations
  2 import asyncio
  3 ...
"""

from __future__ import annotations

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
class WriteFileData:
    """Parsed write_file result for structured display."""

    filepath: str
    filename: str
    content: str
    line_count: int
    is_success: bool


def parse_write_file_result(
    args: dict[str, Any] | None, result: str
) -> WriteFileData | None:
    """Extract structured data from write_file output."""
    if not result:
        return None

    args = args or {}
    filepath = args.get("filepath", "")
    content = args.get("content", "")

    is_success = "Successfully wrote" in result

    if not filepath and "Successfully wrote to new file:" in result:
        filepath = result.split("Successfully wrote to new file:")[-1].strip()

    if not filepath:
        return None

    line_count = len(content.splitlines()) if content else 0

    return WriteFileData(
        filepath=filepath,
        filename=Path(filepath).name,
        content=content,
        line_count=line_count,
        is_success=is_success,
    )


@tool_renderer("write_file")
def render_write_file(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render write_file with slim NeXTSTEP panel style.

    Dream mockup format:
    ─ write_file ─────────────────────── 25 lines NEW
      ↳ src/tunacode/ui/new_module.py

      1 from __future__ import annotations
      2 import asyncio
    """
    data = parse_write_file_result(args, result)
    if data is None:
        return None

    # Build stats with NEW indicator
    stats = f"{data.line_count} lines NEW"

    # Build viewport with syntax highlighting
    if not data.content:
        viewport = Text("(empty file)", style="dim italic")
    else:
        lines = data.content.splitlines()
        max_display = TOOL_VIEWPORT_LINES

        preview_lines: list[str] = []
        for i, line in enumerate(lines):
            if i >= max_display:
                break
            preview_lines.append(truncate_line(line, max_width=80))

        while len(preview_lines) < MIN_VIEWPORT_LINES:
            preview_lines.append("")

        preview_content = "\n".join(preview_lines)

        viewport = syntax_or_text(
            preview_content,
            filepath=data.filepath,
            line_numbers=True,
        )

    # Footer
    shown = min(data.line_count, TOOL_VIEWPORT_LINES)
    footer = slim_footer(shown, data.line_count)

    return slim_panel(
        name="write_file",
        content=viewport,
        stats=stats,
        subtitle=data.filepath,
        footer=footer if str(footer) else None,
    )
