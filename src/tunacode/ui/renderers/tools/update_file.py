"""NeXTSTEP-style panel renderer for update_file tool output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from rich.console import Group, RenderableType
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from tunacode.core.ui_api.constants import MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES

from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    ToolRenderResult,
    build_hook_path_params,
    clamp_content_width,
    tool_renderer,
    truncate_line,
)
from tunacode.ui.widgets.chat import PanelMeta

# Width reserve in the side-by-side diff view: both line numbers + lane gutters.
_DIFF_LINE_WIDTH_RESERVE: int = 13
_DIFF_LINE_NUMBER_MIN_WIDTH: int = 3
_DIFF_CONTENT_MIN_WIDTH: int = 12
_CHANGE_LANE_WIDTH: int = 2
_SIDE_BY_SIDE_DIVIDER: str = "│"


@dataclass(frozen=True)
class UpdateFileData:
    """Parsed update_file result for structured display."""

    filepath: str
    filename: str
    root_path: Path
    message: str
    diff_content: str
    additions: int
    deletions: int
    hunks: int
    diagnostics_block: str | None = None


DiffLineKind = Literal["context", "insert", "delete", "meta", "pad"]


@dataclass(frozen=True)
class DiffSideBySideLine:
    """Normalized diff row for side-by-side rendering."""

    left_line_no: int | None
    left_content: str
    right_line_no: int | None
    right_content: str
    kind: DiffLineKind


class UpdateFileRenderer(BaseToolRenderer[UpdateFileData]):
    """Renderer for update_file output with optional diagnostics zone."""

    _hunk_header = re.compile(
        r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
        r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
    )

    def parse_result(self, args: dict[str, Any] | None, result: str) -> UpdateFileData | None:
        """Extract structured data from update_file output."""
        if not result:
            return None

        # Extract diagnostics block before parsing diff
        from tunacode.ui.renderers.tools.diagnostics import extract_diagnostics_from_result

        result_clean, diagnostics_block = extract_diagnostics_from_result(result)

        # Split message from diff
        if "\n--- a/" not in result_clean:
            return None

        parts = result_clean.split("\n--- a/", 1)
        message = parts[0].strip()
        diff_content = "--- a/" + parts[1]

        # Extract filepath from diff header
        filepath_match = re.search(r"--- a/(.+)", diff_content)
        if not filepath_match:
            args = args or {}
            filepath = args.get("filepath", "unknown")
        else:
            filepath = filepath_match.group(1).strip()
        root_path = Path.cwd()

        additions = 0
        deletions = 0
        hunks = 0

        for line in diff_content.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
            elif line.startswith("@@"):
                hunks += 1

        return UpdateFileData(
            filepath=filepath,
            filename=Path(filepath).name,
            root_path=root_path,
            message=message,
            diff_content=diff_content,
            additions=additions,
            deletions=deletions,
            hunks=hunks,
            diagnostics_block=diagnostics_block,
        )

    def build_header(
        self,
        data: UpdateFileData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 1: Filename + change stats."""
        header = Text()
        header.append(data.filename, style="bold")
        header.append("   ", style="")
        header.append(f"+{data.additions}", style="green")
        header.append(" ", style="")
        header.append(f"-{data.deletions}", style="red")
        return header

    def build_params(self, data: UpdateFileData, max_line_width: int) -> Text:
        """Zone 2: Full filepath."""
        return build_hook_path_params(data.filepath, data.root_path)

    def _parse_side_by_side_rows(self, diff: str) -> list[DiffSideBySideLine]:
        """Convert unified diff text into side-by-side row objects."""
        rows: list[DiffSideBySideLine] = []
        left_line_no: int | None = None
        right_line_no: int | None = None

        for line in diff.splitlines():
            hunk_match = self._hunk_header.match(line)
            if hunk_match is not None:
                left_line_no = int(hunk_match.group("old_start"))
                right_line_no = int(hunk_match.group("new_start"))
                continue

            if line.startswith("--- a/") or line.startswith("+++ b/"):
                continue

            if left_line_no is None or right_line_no is None:
                continue

            if line.startswith("\\"):
                rows.append(DiffSideBySideLine(None, "", None, "", "meta"))
                continue

            if line.startswith("-") and not line.startswith("---"):
                rows.append(DiffSideBySideLine(left_line_no, line[1:], None, "", "delete"))
                left_line_no += 1
                continue

            if line.startswith("+") and not line.startswith("+++"):
                rows.append(DiffSideBySideLine(None, "", right_line_no, line[1:], "insert"))
                right_line_no += 1
                continue

            if line.startswith(" "):
                content = line[1:]
                rows.append(
                    DiffSideBySideLine(
                        left_line_no,
                        content,
                        right_line_no,
                        content,
                        "context",
                    )
                )
                left_line_no += 1
                right_line_no += 1
                continue

            if line:
                rows.append(
                    DiffSideBySideLine(
                        left_line_no,
                        line,
                        right_line_no,
                        line,
                        "context",
                    )
                )
                left_line_no += 1
                right_line_no += 1

        return rows

    def _truncate_side_by_side_rows(
        self,
        rows: list[DiffSideBySideLine],
        max_lines: int = TOOL_VIEWPORT_LINES,
    ) -> tuple[list[DiffSideBySideLine], int, int]:
        """Truncate rows for viewport and return (rows, shown, total)."""
        total = len(rows)
        if total <= max_lines:
            return rows, total, total
        return rows[:max_lines], max_lines, total

    def _side_by_side_widths(
        self,
        rows: list[DiffSideBySideLine],
        max_line_width: int,
    ) -> tuple[int, int, int]:
        """Calculate widths for the diff table columns."""
        max_left = 0
        max_right = 0
        for row in rows:
            if row.left_line_no is not None:
                max_left = max(max_left, row.left_line_no)
            if row.right_line_no is not None:
                max_right = max(max_right, row.right_line_no)

        line_no_width = max(
            len(str(max_left)),
            len(str(max_right)),
            _DIFF_LINE_NUMBER_MIN_WIDTH,
        )
        content_width = clamp_content_width(
            max_line_width=max_line_width,
            reserved_width=(line_no_width * 2) + _DIFF_LINE_WIDTH_RESERVE,
        )
        left_width = max(_DIFF_CONTENT_MIN_WIDTH, content_width // 2)
        right_width = max(_DIFF_CONTENT_MIN_WIDTH, content_width - left_width)
        return line_no_width, left_width, right_width

    def _build_side_by_side_viewport(
        self,
        rows: list[DiffSideBySideLine],
        max_line_width: int,
        filename: str,
    ) -> RenderableType:
        """Build the side-by-side diff table."""
        line_no_width, left_width, right_width = self._side_by_side_widths(rows, max_line_width)

        table = Table.grid(padding=(0, 1), expand=True)
        table.add_column("a", width=line_no_width, justify="right", style="dim")
        table.add_column("left", width=left_width, overflow="fold")
        table.add_column("", width=_CHANGE_LANE_WIDTH, justify="center")
        table.add_column("b", width=line_no_width, justify="right", style="dim")
        table.add_column("right", width=right_width, overflow="fold")
        table.caption = f"Before: a/{filename}  {_SIDE_BY_SIDE_DIVIDER}  After: b/{filename}"
        table.caption_style = "dim"

        kind_styles: dict[DiffLineKind, tuple[str, str]] = {
            "context": ("", ""),
            "insert": ("dim", "green"),
            "delete": ("red", "dim"),
            "meta": ("dim", "dim"),
            "pad": ("dim", "dim"),
        }
        lane_styles: dict[DiffLineKind, str] = {
            "context": "dim",
            "insert": "green",
            "delete": "red",
            "meta": "yellow",
            "pad": "dim",
        }
        kind_marks: dict[DiffLineKind, str] = {
            "context": f" {_SIDE_BY_SIDE_DIVIDER}",
            "insert": f"+{_SIDE_BY_SIDE_DIVIDER}",
            "delete": f"-{_SIDE_BY_SIDE_DIVIDER}",
            "meta": f"!{_SIDE_BY_SIDE_DIVIDER}",
            "pad": f" {_SIDE_BY_SIDE_DIVIDER}",
        }

        for row in rows:
            left_style, right_style = kind_styles[row.kind]
            lane_style = lane_styles[row.kind]
            left_number = "" if row.left_line_no is None else str(row.left_line_no)
            right_number = "" if row.right_line_no is None else str(row.right_line_no)
            left_text = truncate_line(row.left_content, left_width)
            right_text = truncate_line(row.right_content, right_width)

            table.add_row(
                Text(left_number, style="dim"),
                Text(left_text, style=left_style),
                Text(kind_marks[row.kind], style=lane_style),
                Text(right_number, style="dim"),
                Text(right_text, style=right_style),
            )

        return table

    def build_viewport(self, data: UpdateFileData, max_line_width: int) -> RenderableType:
        """Zone 3: Diff viewport with syntax highlighting."""
        side_by_side_rows = self._parse_side_by_side_rows(data.diff_content)

        if side_by_side_rows:
            visible_rows, _, _ = self._truncate_side_by_side_rows(side_by_side_rows)
            while len(visible_rows) < MIN_VIEWPORT_LINES:
                visible_rows.append(DiffSideBySideLine(None, "", None, "", "pad"))
            return self._build_side_by_side_viewport(
                visible_rows,
                max_line_width,
                data.filename,
            )

        # Fallback to unified diff if row parsing fails.
        truncated_diff, _, _ = self._truncate_diff(data.diff_content, max_line_width)
        diff_lines = truncated_diff.split("\n")
        while len(diff_lines) < MIN_VIEWPORT_LINES:
            diff_lines.append("")
        truncated_diff = "\n".join(diff_lines)
        return Syntax(truncated_diff, "diff", theme="monokai", word_wrap=True)

    def _truncate_diff(self, diff: str, max_line_width: int) -> tuple[str, int, int]:
        """Truncate diff content, return (truncated, shown, total)."""
        lines = diff.splitlines()
        total = len(lines)
        max_content = TOOL_VIEWPORT_LINES
        visible_lines = lines[:max_content]

        if total <= max_content:
            return "\n".join(visible_lines), total, total
        return "\n".join(visible_lines), max_content, total

    def build_status(
        self,
        data: UpdateFileData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 4: Status with hunks, truncation info, and timing."""
        status_items: list[str] = []

        hunk_word = "hunk" if data.hunks == 1 else "hunks"
        status_items.append(f"{data.hunks} {hunk_word}")

        _, shown, total = self._truncate_side_by_side_rows(
            self._parse_side_by_side_rows(data.diff_content)
        )
        if shown < total:
            status_items.append(f"[{shown}/{total} lines]")

        if duration_ms is not None:
            status_items.append(f"{duration_ms:.0f}ms")

        return Text("  ".join(status_items), style="dim") if status_items else Text("")

    def render(
        self,
        args: dict[str, Any] | None,
        result: str,
        duration_ms: float | None,
        max_line_width: int,
    ) -> ToolRenderResult:
        """Render update_file with NeXTSTEP zoned layout plus optional diagnostics."""
        data = self.parse_result(args, result)
        if data is None:
            return None

        header = self.build_header(data, duration_ms, max_line_width)
        params = self.build_params(data, max_line_width)
        viewport = self.build_viewport(data, max_line_width)
        status = self.build_status(data, duration_ms, max_line_width)
        separator = self.build_separator()

        content_parts: list[RenderableType] = [
            header,
            Text("\n"),
        ]

        if params is not None:
            content_parts.extend([params, Text("\n")])

        content_parts.extend(
            [
                separator,
                Text("\n"),
                viewport,
                Text("\n"),
                separator,
                Text("\n"),
                status,
            ]
        )

        # Add diagnostics zone if present
        if data.diagnostics_block:
            from tunacode.ui.renderers.tools.diagnostics import (
                parse_diagnostics_block,
                render_diagnostics_inline,
            )

            diag_data = parse_diagnostics_block(data.diagnostics_block)
            if diag_data and diag_data.items:
                content_parts.extend(
                    [
                        Text("\n"),
                        separator,
                        Text("\n"),
                        render_diagnostics_inline(diag_data),
                    ]
                )

        content = Group(*content_parts)

        timestamp = datetime.now().strftime("%H:%M:%S")
        border_color = self.get_border_color(data)
        status_text = self.get_status_text(data)

        meta = PanelMeta(
            css_class="tool-panel",
            border_title=f"[{border_color}]{self.config.tool_name}[/] [{status_text}]",
            border_subtitle=f"[{self.config.muted_color}]{timestamp}[/]",
        )

        return content, meta


# Module-level renderer instance
_renderer = UpdateFileRenderer(RendererConfig(tool_name="update_file"))


@tool_renderer("update_file")
def render_update_file(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None,
    max_line_width: int,
) -> ToolRenderResult:
    """Render update_file with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms, max_line_width)
