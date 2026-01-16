"""NeXTSTEP-style panel renderer for list_dir tool output.

Displays directory tree with styled entries - directories bold, files colored by type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import MAX_PANEL_LINE_WIDTH, MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES
from tunacode.tools.list_dir import IGNORE_PATTERNS_COUNT
from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    build_hook_params_prefix,
    tool_renderer,
    truncate_line,
)
from tunacode.ui.renderers.tools.syntax_utils import get_lexer


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
    # Computed during parsing for status zone
    shown_lines: int = 0
    total_lines: int = 0


class ListDirRenderer(BaseToolRenderer[ListDirData]):
    """Renderer for list_dir tool output."""

    def parse_result(self, args: dict[str, Any] | None, result: str) -> ListDirData | None:
        """Parse list_dir output into structured data."""
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

    def build_header(
        self,
        data: ListDirData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Build header with directory path and counts."""
        header = Text()
        header.append(data.directory, style="bold")
        header.append(f"   {data.file_count} files  {data.dir_count} dirs", style="dim")
        return header

    def build_params(self, data: ListDirData, max_line_width: int) -> Text:
        """Build parameter display line."""
        hidden_val = "on" if data.show_hidden else "off"
        params = build_hook_params_prefix()
        params.append("hidden:", style="dim")
        params.append(f" {hidden_val}", style="dim bold")
        params.append("  max:", style="dim")
        params.append(f" {data.max_files}", style="dim bold")
        params.append("  ignore:", style="dim")
        params.append(f" {data.ignore_count}", style="dim bold")
        return params

    def _get_file_style(self, name: str) -> str:
        """Get style based on file name/extension."""
        lexer = get_lexer(name)

        # Color by type
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

    def _style_tree_line(self, line: str) -> Text:
        """Style a tree line with appropriate colors."""
        styled = Text()

        # Extract tree prefix (├──, │  , └──, etc) and name
        tree_chars = "├└│─ "
        prefix_end = 0
        for i, char in enumerate(line):
            if char in tree_chars:
                prefix_end = i + 1
            else:
                break

        prefix = line[:prefix_end]
        name = line[prefix_end:].strip()

        # Tree structure in dim
        styled.append(prefix, style="dim")

        # Determine if directory or file
        is_dir = name.endswith("/") or "." not in name

        if is_dir:
            # Directories in bold cyan
            styled.append(name, style="bold cyan")
        else:
            # Files colored by type
            style = self._get_file_style(name)
            styled.append(name, style=style or "")

        return styled

    def build_viewport(self, data: ListDirData, max_line_width: int) -> RenderableType:
        """Build styled tree content viewport."""
        # Skip first line (dirname already in header)
        tree_lines = data.tree_content.splitlines()[1:]

        if not tree_lines:
            return Text("(empty directory)", style="dim italic")

        viewport_parts: list[RenderableType] = []
        max_display = TOOL_VIEWPORT_LINES
        lines_used = 0

        for line in tree_lines:
            if lines_used >= max_display:
                break

            truncated = truncate_line(line, max_width=max_line_width)
            styled_line = self._style_tree_line(truncated)
            viewport_parts.append(styled_line)
            lines_used += 1

        # Store for status zone
        data.shown_lines = lines_used
        data.total_lines = len(tree_lines)

        # Pad to minimum height
        while lines_used < MIN_VIEWPORT_LINES:
            viewport_parts.append(Text(""))
            lines_used += 1

        return Group(*viewport_parts)

    def build_status(
        self,
        data: ListDirData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Build status line with truncation info and timing."""
        status_items: list[str] = []

        if data.is_truncated:
            status_items.append("(truncated)")
        if data.shown_lines < data.total_lines:
            status_items.append(f"[{data.shown_lines}/{data.total_lines} lines]")
        if duration_ms is not None:
            status_items.append(f"{duration_ms:.0f}ms")

        return Text("  ".join(status_items), style="dim") if status_items else Text("")


# Module-level renderer instance
_renderer = ListDirRenderer(RendererConfig(tool_name="list_dir"))


@tool_renderer("list_dir")
def render_list_dir(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
    max_line_width: int = MAX_PANEL_LINE_WIDTH,
) -> RenderableType | None:
    """Render list_dir with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms, max_line_width)
