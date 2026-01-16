"""Slim NeXTSTEP-style panel renderer for list_dir tool output.

Dream mockup style:
─ list_dir ─────────────────── 45 files · 12 dirs
  ↳ src/tunacode/ui/

├── __init__.py
├── app.py
├── renderers/
│   ├── panels.py
│   └── tools/
...
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES
from tunacode.ui.renderers.tools.base import tool_renderer, truncate_line
from tunacode.ui.renderers.tools.slim_base import slim_footer, slim_panel
from tunacode.ui.renderers.tools.syntax_utils import get_lexer


@dataclass
class ListDirData:
    """Parsed list_dir result for structured display."""

    directory: str
    tree_content: str
    file_count: int
    dir_count: int
    is_truncated: bool
    total_lines: int = 0


def parse_list_dir_result(
    args: dict[str, Any] | None, result: str
) -> ListDirData | None:
    """Parse list_dir output into structured data."""
    if not result:
        return None

    lines = result.strip().splitlines()
    if len(lines) < 2:
        return None

    summary_line = lines[0]
    summary_match = re.match(
        r"(\d+)\s+files\s+(\d+)\s+dirs(?:\s+\(truncated\))?", summary_line
    )

    if not summary_match:
        return None

    file_count = int(summary_match.group(1))
    dir_count = int(summary_match.group(2))
    is_truncated = "(truncated)" in summary_line

    directory = lines[1].rstrip("/")
    tree_content = "\n".join(lines[1:])

    return ListDirData(
        directory=directory,
        tree_content=tree_content,
        file_count=file_count,
        dir_count=dir_count,
        is_truncated=is_truncated,
        total_lines=len(lines) - 1,
    )


def _get_file_style(name: str) -> str:
    """Get style based on file name/extension."""
    lexer = get_lexer(name)

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

    return ""


def _style_tree_line(line: str) -> Text:
    """Style a tree line with appropriate colors."""
    styled = Text()

    tree_chars = "├└│─ "
    prefix_end = 0
    for i, char in enumerate(line):
        if char in tree_chars:
            prefix_end = i + 1
        else:
            break

    prefix = line[:prefix_end]
    name = line[prefix_end:].strip()

    styled.append(prefix, style="dim")

    is_dir = name.endswith("/") or "." not in name

    if is_dir:
        styled.append(name, style="bold cyan")
    else:
        style = _get_file_style(name)
        styled.append(name, style=style or "")

    return styled


@tool_renderer("list_dir")
def render_list_dir(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render list_dir with slim NeXTSTEP panel style.

    Dream mockup format:
    ─ list_dir ─────────────────── 45 files · 12 dirs
      ↳ src/tunacode/ui/

    ├── __init__.py
    ├── app.py
    └── renderers/
    """
    data = parse_list_dir_result(args, result)
    if data is None:
        return None

    # Build stats
    stats = f"{data.file_count} files · {data.dir_count} dirs"

    # Build viewport
    tree_lines = data.tree_content.splitlines()[1:]

    if not tree_lines:
        viewport = Text("(empty directory)", style="dim italic")
        shown = 0
    else:
        viewport_parts: list[RenderableType] = []
        max_display = TOOL_VIEWPORT_LINES
        lines_used = 0

        for line in tree_lines:
            if lines_used >= max_display:
                break

            truncated = truncate_line(line, max_width=60)
            styled_line = _style_tree_line(truncated)
            viewport_parts.append(styled_line)
            lines_used += 1

        shown = lines_used

        while lines_used < MIN_VIEWPORT_LINES:
            viewport_parts.append(Text(""))
            lines_used += 1

        viewport = Group(*viewport_parts)

    # Footer
    footer = slim_footer(shown, len(tree_lines))

    return slim_panel(
        name="list_dir",
        content=viewport,
        stats=stats,
        subtitle=data.directory,
        footer=footer if str(footer) else None,
    )
