"""Slim NeXTSTEP-style panel renderer for update_file tool output.

Dream mockup style:
─ update_file ──────────────────────────────────── +3 -2
  ↳ tools/web_fetch.py

136 try:
137     head_response = await client.head(validated_url)
138 - if content_length and int(content_length) > MAX_SIZE:    ██ RED BG
139 + max_content_size = config.max_content_size_bytes         ██ GREEN BG
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import (
    MAX_PANEL_LINE_WIDTH,
    SLIM_PANEL_WIDTH,
    TOOL_VIEWPORT_LINES,
)
from tunacode.ui.renderers.tools.base import tool_renderer
from tunacode.ui.renderers.tools.slim_base import (
    STYLE_ADDED,
    STYLE_REMOVED,
    slim_footer,
    slim_panel,
    styled_line,
)


@dataclass
class UpdateFileData:
    """Parsed update_file result for structured display."""

    filepath: str
    filename: str
    message: str
    diff_content: str
    additions: int
    deletions: int
    hunks: int
    diagnostics_block: str | None = None


def parse_update_file_result(
    args: dict[str, Any] | None, result: str
) -> UpdateFileData | None:
    """Extract structured data from update_file output.

    Expected format:
        File 'path/to/file.py' updated successfully.

        --- a/path/to/file.py
        +++ b/path/to/file.py
        @@ -10,5 +10,7 @@
        ...diff content...

        <file_diagnostics>
        Error (line 10): type mismatch
        </file_diagnostics>
    """
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

    # Count additions and deletions
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

    # Extract just filename from path
    filename = filepath.split("/")[-1] if "/" in filepath else filepath

    return UpdateFileData(
        filepath=filepath,
        filename=filename,
        message=message,
        diff_content=diff_content,
        additions=additions,
        deletions=deletions,
        hunks=hunks,
        diagnostics_block=diagnostics_block,
    )


def build_diff_viewport(
    diff_content: str,
    max_lines: int = TOOL_VIEWPORT_LINES,
    max_width: int = MAX_PANEL_LINE_WIDTH,
) -> tuple[RenderableType, int, int]:
    """Build diff viewport with full-line background colors.

    Args:
        diff_content: Raw diff string
        max_lines: Maximum lines to show
        max_width: Maximum line width

    Returns:
        Tuple of (renderable, lines_shown, total_lines)
    """
    lines = diff_content.splitlines()

    # Skip header lines (---, +++, @@)
    content_lines: list[tuple[str, str, int | None]] = []
    current_line_num = 0

    for line in lines:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            # Parse line number from hunk header: @@ -10,5 +10,7 @@
            match = re.search(r"\+(\d+)", line)
            if match:
                current_line_num = int(match.group(1))
            continue

        # Determine line type and number
        if line.startswith("+"):
            line_type = "added"
            display_num = current_line_num
            current_line_num += 1
        elif line.startswith("-"):
            line_type = "removed"
            display_num = current_line_num
            # Don't increment for removed lines
        else:
            line_type = "context"
            display_num = current_line_num
            current_line_num += 1

        content_lines.append((line, line_type, display_num))

    total = len(content_lines)
    shown = min(total, max_lines)
    display_lines = content_lines[:shown]

    # Build viewport
    viewport_parts: list[RenderableType] = []

    for line_content, line_type, line_num in display_lines:
        # Format: "139 - old code" or "139 + new code"
        prefix = f"{line_num:3d} " if line_num else "    "

        # Truncate if too long
        display_content = line_content
        if len(display_content) > max_width - 4:
            display_content = display_content[: max_width - 7] + "..."

        full_line = f"{prefix}{display_content}"

        if line_type == "added":
            viewport_parts.append(styled_line(full_line, STYLE_ADDED, SLIM_PANEL_WIDTH))
        elif line_type == "removed":
            viewport_parts.append(
                styled_line(full_line, STYLE_REMOVED, SLIM_PANEL_WIDTH)
            )
        else:
            viewport_parts.append(Text(full_line))

    return Group(*viewport_parts), shown, total


@tool_renderer("update_file")
def render_update_file(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render update_file with slim NeXTSTEP panel style.

    Dream mockup format:
    ─ update_file ──────────────────────────────── +3 -2
      ↳ tools/web_fetch.py

    139 - if content_length > MAX_SIZE:                     ██ RED
    139 + max_content_size = config.max_size                ██ GREEN
    140 + if content_length > max_content_size:             ██ GREEN
    """
    data = parse_update_file_result(args, result)
    if data is None:
        return None

    # Build stats string
    stats = f"+{data.additions} -{data.deletions}"

    # Build diff viewport with full-line backgrounds
    viewport, shown, total = build_diff_viewport(data.diff_content)

    # Add diagnostics if present
    content_parts: list[RenderableType] = [viewport]
    if data.diagnostics_block:
        from tunacode.ui.renderers.tools.diagnostics import (
            parse_diagnostics_block,
            render_diagnostics_slim,
        )

        diag_data = parse_diagnostics_block(data.diagnostics_block)
        if diag_data and diag_data.items:
            content_parts.append(Text(""))
            content_parts.append(render_diagnostics_slim(diag_data))

    content = Group(*content_parts) if len(content_parts) > 1 else viewport

    # Build footer if truncated
    footer = slim_footer(shown, total)

    return slim_panel(
        name="update_file",
        content=content,
        stats=stats,
        subtitle=data.filepath,
        footer=footer if str(footer) else None,
    )
