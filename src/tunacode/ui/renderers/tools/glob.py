"""NeXTSTEP-style panel renderer for glob tool output.

Displays file list with styled paths - directories vs files distinguished.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import MAX_PANEL_LINE_WIDTH, MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES
from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    tool_renderer,
)
from tunacode.ui.renderers.tools.syntax_utils import get_lexer


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


class GlobRenderer(BaseToolRenderer[GlobData]):
    """Renderer for glob tool output."""

    def parse_result(self, args: dict[str, Any] | None, result: str) -> GlobData | None:
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

    def _truncate_path(self, path: str) -> str:
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

    def build_header(self, data: GlobData, duration_ms: float | None) -> Text:
        """Zone 1: Pattern + file count."""
        header = Text()
        header.append(f'"{data.pattern}"', style="bold")
        file_word = "file" if data.file_count == 1 else "files"
        header.append(f"   {data.file_count} {file_word}", style="dim")
        return header

    def build_params(self, data: GlobData) -> Text:
        """Zone 2: Parameters (recursive, hidden, sort)."""
        recursive_val = "on" if data.recursive else "off"
        hidden_val = "on" if data.include_hidden else "off"
        params = Text()
        params.append("recursive:", style="dim")
        params.append(f" {recursive_val}", style="dim bold")
        params.append("  hidden:", style="dim")
        params.append(f" {hidden_val}", style="dim bold")
        params.append("  sort:", style="dim")
        params.append(f" {data.sort_by}", style="dim bold")
        return params

    def _get_file_style(self, filepath: str) -> str:
        """Get style based on file type."""
        lexer = get_lexer(filepath)
        path = Path(filepath)

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
        if path.suffix in (".test.py", ".spec.ts", ".test.ts", ".spec.js", ".test.js"):
            return "bright_green"

        return ""

    def build_viewport(self, data: GlobData) -> RenderableType:
        """Zone 3: Styled file list viewport."""
        if not data.files:
            return Text("(no files)", style="dim italic")

        viewport_parts: list[RenderableType] = []
        max_display = TOOL_VIEWPORT_LINES
        lines_used = 0

        for filepath in data.files:
            if lines_used >= max_display:
                break

            truncated = self._truncate_path(filepath)
            path = Path(filepath)
            style = self._get_file_style(filepath)

            line = Text()
            # Show directory in dim, filename in color
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

        # Pad to minimum height
        while lines_used < MIN_VIEWPORT_LINES:
            viewport_parts.append(Text(""))
            lines_used += 1

        return Group(*viewport_parts)

    def build_status(self, data: GlobData, duration_ms: float | None) -> Text:
        """Zone 4: Status with source, truncation info, timing."""
        from tunacode.constants import TOOL_VIEWPORT_LINES

        status_items: list[str] = []

        # Source indicator (cache hit/miss)
        if data.source == "index":
            status_items.append("indexed")
        else:
            status_items.append("scanned")

        if data.is_truncated or len(data.files) < data.file_count:
            shown = min(len(data.files), TOOL_VIEWPORT_LINES)
            status_items.append(f"[{shown}/{data.file_count} shown]")

        if duration_ms is not None:
            status_items.append(f"{duration_ms:.0f}ms")

        return Text("  ".join(status_items), style="dim") if status_items else Text("")


# Module-level renderer instance
_renderer = GlobRenderer(RendererConfig(tool_name="glob"))


@tool_renderer("glob")
def render_glob(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render glob with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms)
