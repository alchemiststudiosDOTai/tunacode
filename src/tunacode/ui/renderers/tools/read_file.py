"""NeXTSTEP-style panel renderer for read_file tool output.

Displays file contents with syntax highlighting based on file extension.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import RenderableType
from rich.text import Text

from tunacode.constants import SYNTAX_LINE_NUMBER_PADDING, SYNTAX_LINE_NUMBER_SEPARATOR_WIDTH

from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    build_hook_path_params,
    clamp_content_width,
    tool_renderer,
)
from tunacode.ui.renderers.tools.syntax_utils import syntax_or_text


@dataclass
class ReadFileData:
    """Parsed read_file result for structured display."""

    filepath: str
    filename: str
    root_path: Path
    content_lines: list[tuple[int, str]]  # (line_number, content)
    total_lines: int
    offset: int
    has_more: bool
    end_message: str


class ReadFileRenderer(BaseToolRenderer[ReadFileData]):
    """Renderer for read_file tool output."""

    def parse_result(self, args: dict[str, Any] | None, result: str) -> ReadFileData | None:
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
        root_path = Path.cwd()

        # If total_lines not found in message, estimate from content
        if total_lines == 0:
            total_lines = content_lines[-1][0] if content_lines else 0

        return ReadFileData(
            filepath=filepath,
            filename=Path(filepath).name,
            root_path=root_path,
            content_lines=content_lines,
            total_lines=total_lines,
            offset=offset,
            has_more=has_more,
            end_message=end_message,
        )

    def build_header(
        self,
        data: ReadFileData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 1: Filename + line range."""
        header = Text()
        header.append(data.filename, style="bold")

        if data.content_lines:
            start_line = data.content_lines[0][0]
            end_line = data.content_lines[-1][0]
            header.append(f"   lines {start_line}-{end_line}", style="dim")

        return header

    def build_params(self, data: ReadFileData, max_line_width: int) -> Text:
        """Zone 2: Full filepath."""
        params = build_hook_path_params(data.filepath, data.root_path)
        return params

    def build_viewport(self, data: ReadFileData, max_line_width: int) -> RenderableType:
        """Zone 3: Syntax-highlighted content viewport."""
        from tunacode.constants import MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES

        if not data.content_lines:
            return Text("(empty file)", style="dim italic")

        max_display = TOOL_VIEWPORT_LINES
        start_line = data.content_lines[0][0] if data.content_lines else 1
        end_index = min(len(data.content_lines), max_display) - 1
        end_line = data.content_lines[end_index][0] if end_index >= 0 else start_line
        line_number_digits = len(str(end_line))
        line_number_gutter = (
            line_number_digits + SYNTAX_LINE_NUMBER_PADDING + SYNTAX_LINE_NUMBER_SEPARATOR_WIDTH
        )
        code_width = clamp_content_width(max_line_width, line_number_gutter)

        # Extract just the content without line numbers for syntax highlighting
        content_only: list[str] = []
        for i, (_line_num, line_content) in enumerate(data.content_lines):
            if i >= max_display:
                break
            content_only.append(line_content)

        # Pad to minimum height
        while len(content_only) < MIN_VIEWPORT_LINES:
            content_only.append("")

        code_content = "\n".join(content_only)
        # Use syntax highlighting with line numbers
        return syntax_or_text(
            code_content,
            filepath=data.filepath,
            line_numbers=True,
            start_line=start_line,
            code_width=code_width,
        )

    def build_status(
        self,
        data: ReadFileData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 4: Status with continuation info and timing."""
        from tunacode.constants import TOOL_VIEWPORT_LINES

        status_items: list[str] = []

        shown = min(len(data.content_lines), TOOL_VIEWPORT_LINES)
        if shown < len(data.content_lines):
            status_items.append(f"[{shown}/{len(data.content_lines)} displayed]")

        if data.has_more:
            status_items.append(f"total: {data.total_lines} lines")
            status_items.append("(more available)")
        elif data.total_lines > 0:
            status_items.append(f"total: {data.total_lines} lines")

        if duration_ms is not None:
            status_items.append(f"{duration_ms:.0f}ms")

        return Text("  ".join(status_items), style="dim") if status_items else Text("")


# Module-level renderer instance
_renderer = ReadFileRenderer(RendererConfig(tool_name="read_file"))


@tool_renderer("read_file")
def render_read_file(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None,
    max_line_width: int,
) -> RenderableType | None:
    """Render read_file with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms, max_line_width)
