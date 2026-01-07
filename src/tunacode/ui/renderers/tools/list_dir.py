"""NeXTSTEP-style panel renderer for list_dir tool output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rich.console import RenderableType
from rich.text import Text

from tunacode.tools.list_dir import IGNORE_PATTERNS_COUNT
from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    pad_lines,
    tool_renderer,
    truncate_content,
)


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

    def build_header(self, data: ListDirData, duration_ms: float | None) -> Text:
        """Build header with directory path and counts."""
        header = Text()
        header.append(data.directory, style="bold")
        header.append(f"   {data.file_count} files  {data.dir_count} dirs", style="dim")
        return header

    def build_params(self, data: ListDirData) -> Text:
        """Build parameter display line."""
        hidden_val = "on" if data.show_hidden else "off"
        params = Text()
        params.append("hidden:", style="dim")
        params.append(f" {hidden_val}", style="dim bold")
        params.append("  max:", style="dim")
        params.append(f" {data.max_files}", style="dim bold")
        params.append("  ignore:", style="dim")
        params.append(f" {data.ignore_count}", style="dim bold")
        return params

    def build_viewport(self, data: ListDirData) -> RenderableType:
        """Build tree content viewport."""
        # Skip first line (dirname already in header)
        tree_lines = data.tree_content.splitlines()[1:]
        tree_only = "\n".join(tree_lines) if tree_lines else "(empty)"

        truncated_tree, shown, total = truncate_content(tree_only)

        # Store for status zone
        data.shown_lines = shown
        data.total_lines = total

        padded = pad_lines(truncated_tree.split("\n"))
        return Text("\n".join(padded))

    def build_status(self, data: ListDirData, duration_ms: float | None) -> Text:
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
) -> RenderableType | None:
    """Render list_dir with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms)
