"""NeXTSTEP-style panel renderer for write_file tool output.

Displays newly created file with syntax-highlighted preview.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import RenderableType
from rich.text import Text

from tunacode.constants import (
    MIN_VIEWPORT_LINES,
    SYNTAX_LINE_NUMBER_PADDING,
    SYNTAX_LINE_NUMBER_SEPARATOR_WIDTH,
    TOOL_VIEWPORT_LINES,
)
from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    build_hook_path_params,
    clamp_content_width,
    tool_renderer,
)
from tunacode.ui.renderers.tools.syntax_utils import syntax_or_text


@dataclass
class WriteFileData:
    """Parsed write_file result for structured display."""

    filepath: str
    filename: str
    root_path: Path
    content: str
    line_count: int
    is_success: bool


class WriteFileRenderer(BaseToolRenderer[WriteFileData]):
    """Renderer for write_file tool output with syntax-highlighted preview."""

    def parse_result(self, args: dict[str, Any] | None, result: str) -> WriteFileData | None:
        """Extract structured data from write_file output.

        Expected format:
            Successfully wrote to new file: /path/to/file.py
        """
        if not result:
            return None

        args = args or {}
        filepath = args.get("filepath", "")
        content = args.get("content", "")

        is_success = "Successfully wrote" in result

        # Try to get filepath from result if not in args
        if not filepath and "Successfully wrote to new file:" in result:
            filepath = result.split("Successfully wrote to new file:")[-1].strip()

        if not filepath:
            return None

        root_path = Path.cwd()
        line_count = len(content.splitlines()) if content else 0

        return WriteFileData(
            filepath=filepath,
            filename=Path(filepath).name,
            root_path=root_path,
            content=content,
            line_count=line_count,
            is_success=is_success,
        )

    def build_header(
        self,
        data: WriteFileData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 1: Filename + line count."""
        header = Text()
        header.append(data.filename, style="bold green")
        header.append("   ", style="")
        header.append("NEW", style="green bold")
        header.append(f"  {data.line_count} lines", style="dim")
        return header

    def build_params(self, data: WriteFileData, max_line_width: int) -> Text:
        """Zone 2: Full filepath."""
        params = build_hook_path_params(data.filepath, data.root_path)
        return params

    def build_viewport(self, data: WriteFileData, max_line_width: int) -> RenderableType:
        """Zone 3: Syntax-highlighted content preview."""
        if not data.content:
            return Text("(empty file)", style="dim italic")

        # Truncate content for viewport
        lines = data.content.splitlines()
        max_display = TOOL_VIEWPORT_LINES
        end_line = min(len(lines), max_display)
        line_number_digits = len(str(end_line))
        line_number_gutter = (
            line_number_digits + SYNTAX_LINE_NUMBER_PADDING + SYNTAX_LINE_NUMBER_SEPARATOR_WIDTH
        )
        code_width = clamp_content_width(max_line_width, line_number_gutter)

        preview_lines: list[str] = []
        for i, line in enumerate(lines):
            if i >= max_display:
                break
            preview_lines.append(line)

        # Pad to minimum height
        while len(preview_lines) < MIN_VIEWPORT_LINES:
            preview_lines.append("")

        preview_content = "\n".join(preview_lines)

        return syntax_or_text(
            preview_content,
            filepath=data.filepath,
            line_numbers=True,
            code_width=code_width,
        )

    def build_status(
        self,
        data: WriteFileData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 4: Status with truncation info and timing."""
        status_items: list[str] = []

        shown = min(data.line_count, TOOL_VIEWPORT_LINES)
        if shown < data.line_count:
            status_items.append(f"[{shown}/{data.line_count} lines]")

        if duration_ms is not None:
            status_items.append(f"{duration_ms:.0f}ms")

        return Text("  ".join(status_items), style="dim") if status_items else Text("")

    def get_border_color(self, data: WriteFileData) -> str:
        """Green for success."""
        return self.config.success_color


# Module-level renderer instance
_renderer = WriteFileRenderer(RendererConfig(tool_name="write_file"))


@tool_renderer("write_file")
def render_write_file(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None,
    max_line_width: int,
) -> RenderableType | None:
    """Render write_file with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms, max_line_width)
