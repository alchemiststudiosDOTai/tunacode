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

from tunacode.constants import (
    SYNTAX_LINE_NUMBER_PADDING,
    SYNTAX_LINE_NUMBER_SEPARATOR_WIDTH,
)

from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    ToolRenderResult,
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

    def _parse_end_message(self, line: str) -> tuple[str, int, bool] | None:
        """Parse an end-of-file status line. Returns (message, total_lines, has_more) or None."""
        if line.startswith("(File has more"):
            match = re.search(r"beyond line (\d+)", line)
            total = int(match.group(1)) if match else 0
            return line, total, True

        if line.startswith("(End of file"):
            match = re.search(r"total (\d+) lines", line)
            total = int(match.group(1)) if match else 0
            return line, total, False

        return None

    def _extract_file_body(self, result: str) -> str | None:
        """Extract raw file payload between tags, tolerating missing closing tag."""
        file_open_tag = "<file>"
        file_close_tag = "</file>"

        start_index = result.find(file_open_tag)
        if start_index < 0:
            return None

        body_start = start_index + len(file_open_tag)
        file_body = result[body_start:]

        if file_body.startswith("\r\n"):
            file_body = file_body[2:]
        elif file_body.startswith("\n"):
            file_body = file_body[1:]

        close_index = file_body.find(file_close_tag)
        if close_index >= 0:
            file_body = file_body[:close_index]

        normalized_body = file_body.strip("\r\n")
        if not normalized_body:
            return None
        return normalized_body

    def _parse_line_content(self, line: str) -> tuple[int, str] | None:
        """Parse a read_file content line into (line_number, content)."""
        if "|" not in line:
            return None

        line_ref, line_content = line.split("|", 1)

        line_number_text = line_ref
        if ":" in line_ref:
            line_number_text, _hash = line_ref.split(":", 1)

        if not line_number_text.isdigit():
            return None

        return int(line_number_text), line_content

    def _parse_content_lines(
        self, lines: list[str]
    ) -> tuple[list[tuple[int, str]], str, int, bool]:
        """Parse numbered content lines and metadata from raw lines.

        Returns (content_lines, end_message, total_lines, has_more).
        """
        content_lines: list[tuple[int, str]] = []
        end_message = ""
        total_lines = 0
        has_more = False
        for line in lines:
            end_meta = self._parse_end_message(line)
            if end_meta is not None:
                end_message, total_lines, has_more = end_meta
                continue

            parsed_line = self._parse_line_content(line)
            if parsed_line is not None:
                content_lines.append(parsed_line)
        return content_lines, end_message, total_lines, has_more

    def parse_result(self, args: dict[str, Any] | None, result: str) -> ReadFileData | None:
        """Extract structured data from read_file output.

        Expected format:
            <file>
            1:ab|line content
            2:cd|line content
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

        file_body = self._extract_file_body(result)
        if file_body is None:
            return None

        lines = file_body.splitlines()
        if not lines:
            return None

        content_lines, end_message, total_lines, has_more = self._parse_content_lines(lines)

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
            root_path=Path.cwd(),
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
) -> ToolRenderResult:
    """Render read_file with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms, max_line_width)
