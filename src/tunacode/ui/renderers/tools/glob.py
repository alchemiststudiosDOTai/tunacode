"""Slim NeXTSTEP-style panel renderer for glob tool output.

Dream mockup style:
─ glob ───────────────────────────────── 42 files
  ↳ **/*.py

src/tunacode/ui/app.py
src/tunacode/core/agent.py
...
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import MAX_PANEL_LINE_WIDTH, MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES
from tunacode.ui.renderers.tools.base import tool_renderer
from tunacode.ui.renderers.tools.slim_base import slim_footer, slim_panel
from tunacode.ui.renderers.tools.syntax_utils import get_lexer


@dataclass
class GlobData:
    """Parsed glob result for structured display."""

    pattern: str
    file_count: int
    files: list[str]
    source: str
    is_truncated: bool


def parse_glob_result(args: dict[str, Any] | None, result: str) -> GlobData | None:
    """Extract structured data from glob output."""
    if not result:
        return None

    lines = result.strip().splitlines()
    if not lines:
        return None

    source = "filesystem"
    start_idx = 0
    if lines[0].startswith("[source:"):
        marker = lines[0]
        source = marker[8:-1]
        start_idx = 1

    if start_idx >= len(lines):
        return None

    header_line = lines[start_idx]
    header_match = re.match(r"Found (\d+) files? matching pattern: (.+)", header_line)
    if not header_match:
        if "No files found" in header_line:
            return None
        return None

    file_count = int(header_match.group(1))
    pattern = header_match.group(2).strip()

    files: list[str] = []
    is_truncated = False

    for line in lines[start_idx + 1 :]:
        line = line.strip()
        if not line:
            continue
        if line.startswith("(truncated"):
            is_truncated = True
            continue
        if line.startswith("/") or line.startswith("./") or "/" in line:
            files.append(line)

    return GlobData(
        pattern=pattern,
        file_count=file_count,
        files=files,
        source=source,
        is_truncated=is_truncated,
    )


def _truncate_path(path: str) -> str:
    """Truncate a path if too wide, keeping filename visible."""
    if len(path) <= MAX_PANEL_LINE_WIDTH:
        return path

    p = Path(path)
    filename = p.name
    max_dir_len = MAX_PANEL_LINE_WIDTH - len(filename) - 4

    if max_dir_len <= 0:
        return "..." + filename[-(MAX_PANEL_LINE_WIDTH - 3) :]

    dir_part = str(p.parent)
    if len(dir_part) > max_dir_len:
        dir_part = "..." + dir_part[-(max_dir_len - 3) :]

    return f"{dir_part}/{filename}"


def _get_file_style(filepath: str) -> str:
    """Get style based on file type."""
    lexer = get_lexer(filepath)
    path = Path(filepath)

    if lexer == "python":
        return "bright_blue"
    if lexer in ("javascript", "typescript", "jsx", "tsx"):
        return "yellow"
    if lexer in ("json", "yaml", "toml"):
        return "green"
    if lexer in ("markdown", "rst"):
        return "cyan"
    if lexer in ("bash", "zsh"):
        return "magenta"
    if path.suffix in (".test.py", ".spec.ts", ".test.ts", ".spec.js", ".test.js"):
        return "bright_green"

    return ""


@tool_renderer("glob")
def render_glob(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render glob with thin framed panel style.

    Dream mockup format:
    ╭─ glob ───────────────────────────────── 42 files ─╮
    │ ↳ **/*.py                                         │
    │                                                   │
    │ src/tunacode/ui/app.py                            │
    │ src/tunacode/core/agent.py                        │
    ╰───────────────────────────────────────────────────╯
    """
    data = parse_glob_result(args, result)
    if data is None:
        return None

    # Build stats
    file_word = "file" if data.file_count == 1 else "files"
    stats = f"{data.file_count} {file_word}"

    # Build viewport
    if not data.files:
        viewport = Text("(no files)", style="dim italic")
    else:
        viewport_parts: list[RenderableType] = []
        max_display = TOOL_VIEWPORT_LINES
        lines_used = 0

        for filepath in data.files:
            if lines_used >= max_display:
                break

            truncated = _truncate_path(filepath)
            path = Path(filepath)
            style = _get_file_style(filepath)

            line = Text()
            if "/" in truncated:
                dir_part = str(path.parent)
                if len(dir_part) > 30:
                    dir_part = "..." + dir_part[-27:]
                line.append(dir_part + "/", style="dim")
                line.append(path.name, style=style or "bold")
            else:
                line.append(truncated, style=style or "bold")

            viewport_parts.append(line)
            lines_used += 1

        while lines_used < MIN_VIEWPORT_LINES:
            viewport_parts.append(Text(""))
            lines_used += 1

        viewport = Group(*viewport_parts)

    # Footer
    shown = min(len(data.files), TOOL_VIEWPORT_LINES)
    footer = slim_footer(shown, data.file_count)

    return slim_panel(
        name="glob",
        content=viewport,
        stats=stats,
        subtitle=data.pattern,
        footer=footer if str(footer) else None,
    )
