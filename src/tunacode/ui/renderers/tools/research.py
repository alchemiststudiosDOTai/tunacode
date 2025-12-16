"""NeXTSTEP-style panel renderer for research_codebase tool output."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from tunacode.constants import MAX_PANEL_LINE_WIDTH, MAX_PANEL_LINES, UI_COLORS

BOX_HORIZONTAL = "\u2500"
SEPARATOR_WIDTH = 52

# Symbolic constants for magic values
DEFAULT_DIRECTORY = "."
DEFAULT_MAX_FILES = 3
ELLIPSIS_LENGTH = 3
MAX_QUERY_DISPLAY_LENGTH = 60
MAX_DIRECTORIES_DISPLAY = 3
LINES_RESERVED_FOR_HEADER_FOOTER = 4
MIN_LINES_FOR_RECOMMENDATIONS = 2
MAX_FALLBACK_RESULT_LENGTH = 500


@dataclass
class ResearchData:
    """Parsed research_codebase result for structured display."""

    query: str
    directories: list[str]
    max_files: int
    relevant_files: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    code_examples: list[dict[str, str]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    is_error: bool = False
    error_message: str | None = None


def _parse_dict_result(result: str) -> dict[str, Any] | None:
    """Parse dict result from string representation."""
    if not result:
        return None

    # Try direct ast.literal_eval first
    try:
        parsed = ast.literal_eval(result.strip())
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, SyntaxError):
        pass

    # Try to find dict pattern in the result
    dict_pattern = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", result, re.DOTALL)
    if dict_pattern:
        try:
            parsed = ast.literal_eval(dict_pattern.group())
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError):
            pass

    return None


def parse_result(args: dict[str, Any] | None, result: str) -> ResearchData | None:
    """Extract structured data from research_codebase output.

    Expected output format (dict):
        {
            "relevant_files": ["path1", "path2"],
            "key_findings": ["finding1", "finding2"],
            "code_examples": [{"file": "path", "code": "...", "explanation": "..."}],
            "recommendations": ["rec1", "rec2"]
        }
    """
    args = args or {}
    query = args.get("query", "")
    directories = args.get("directories", [DEFAULT_DIRECTORY])
    max_files = args.get("max_files", DEFAULT_MAX_FILES)

    if isinstance(directories, str):
        directories = [directories]

    parsed = _parse_dict_result(result)
    if not parsed:
        # Could not parse - return error state with raw result as finding
        return ResearchData(
            query=query,
            directories=directories,
            max_files=max_files,
            key_findings=[result[:MAX_FALLBACK_RESULT_LENGTH] if result else "No results"],
            is_error=True,
            error_message="Could not parse structured result",
        )

    is_error = parsed.get("error", False)
    error_message = parsed.get("error_message") if is_error else None

    return ResearchData(
        query=query,
        directories=directories,
        max_files=max_files,
        relevant_files=parsed.get("relevant_files", []),
        key_findings=parsed.get("key_findings", []),
        code_examples=parsed.get("code_examples", []),
        recommendations=parsed.get("recommendations", []),
        is_error=is_error,
        error_message=error_message,
    )


def _truncate_line(line: str) -> str:
    """Truncate a single line if too wide."""
    if len(line) > MAX_PANEL_LINE_WIDTH:
        return line[: MAX_PANEL_LINE_WIDTH - ELLIPSIS_LENGTH] + "..."
    return line


def render_research_codebase(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render research_codebase with NeXTSTEP zoned layout.

    Zones:
    - Header: query summary
    - Selection context: directories, max_files
    - Primary viewport: files, findings, recommendations
    - Status: file count, duration
    """
    data = parse_result(args, result)
    if not data:
        return None

    # Zone 1: Query header
    header = Text()
    header.append("Query: ", style="dim")
    query_too_long = len(data.query) > MAX_QUERY_DISPLAY_LENGTH
    query_display = data.query[:MAX_QUERY_DISPLAY_LENGTH] + "..." if query_too_long else data.query
    header.append(f'"{query_display}"', style="bold")

    # Zone 2: Parameters
    dirs_display = ", ".join(data.directories[:MAX_DIRECTORIES_DISPLAY])
    if len(data.directories) > MAX_DIRECTORIES_DISPLAY:
        dirs_display += f" (+{len(data.directories) - MAX_DIRECTORIES_DISPLAY})"

    params = Text()
    params.append("dirs:", style="dim")
    params.append(f" {dirs_display}", style="dim bold")
    params.append("  max_files:", style="dim")
    params.append(f" {data.max_files}", style="dim bold")

    separator = Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")

    # Zone 3: Primary viewport
    viewport_lines: list[Text] = []
    lines_used = 0
    max_viewport_lines = MAX_PANEL_LINES - LINES_RESERVED_FOR_HEADER_FOOTER

    # Error state
    if data.is_error:
        error_text = Text()
        error_text.append("Error: ", style="bold red")
        error_text.append(data.error_message or "Unknown error", style="red")
        viewport_lines.append(error_text)
        lines_used += 1

    # Relevant files section
    if data.relevant_files and lines_used < max_viewport_lines:
        files_header = Text()
        files_header.append("Relevant Files", style="bold")
        files_header.append(f" ({len(data.relevant_files)})", style="dim")
        viewport_lines.append(files_header)
        lines_used += 1

        for filepath in data.relevant_files:
            if lines_used >= max_viewport_lines:
                break
            file_line = Text()
            file_line.append("  - ", style="dim")
            file_line.append(_truncate_line(filepath), style="cyan")
            viewport_lines.append(file_line)
            lines_used += 1

        viewport_lines.append(Text(""))
        lines_used += 1

    # Key findings section
    if data.key_findings and lines_used < max_viewport_lines:
        findings_header = Text()
        findings_header.append("Key Findings", style="bold")
        viewport_lines.append(findings_header)
        lines_used += 1

        for i, finding in enumerate(data.key_findings, 1):
            if lines_used >= max_viewport_lines:
                remaining = len(data.key_findings) - i + 1
                viewport_lines.append(Text(f"  (+{remaining} more)", style="dim italic"))
                lines_used += 1
                break
            finding_line = Text()
            finding_line.append(f"  {i}. ", style="dim")
            # Wrap long findings
            finding_text = _truncate_line(finding)
            finding_line.append(finding_text)
            viewport_lines.append(finding_line)
            lines_used += 1

        viewport_lines.append(Text(""))
        lines_used += 1

    # Recommendations section (if space)
    if data.recommendations and lines_used < max_viewport_lines - MIN_LINES_FOR_RECOMMENDATIONS:
        rec_header = Text()
        rec_header.append("Recommendations", style="bold")
        viewport_lines.append(rec_header)
        lines_used += 1

        for rec in data.recommendations:
            if lines_used >= max_viewport_lines:
                break
            rec_line = Text()
            rec_line.append("  > ", style="dim")
            rec_line.append(_truncate_line(rec), style="italic")
            viewport_lines.append(rec_line)
            lines_used += 1

    # Combine viewport
    viewport = Text("\n").join(viewport_lines) if viewport_lines else Text("(no findings)")

    # Zone 4: Status footer
    status_items: list[str] = []
    status_items.append(f"files: {len(data.relevant_files)}")
    status_items.append(f"findings: {len(data.key_findings)}")
    if duration_ms is not None:
        status_items.append(f"{duration_ms:.0f}ms")

    status = Text("  ".join(status_items), style="dim")

    # Compose all zones
    content = Group(
        header,
        Text("\n"),
        params,
        Text("\n"),
        separator,
        Text("\n"),
        viewport,
        Text("\n"),
        separator,
        Text("\n"),
        status,
    )

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Use error styling if error occurred
    if data.is_error:
        border_color = UI_COLORS["error"]
        title_color = UI_COLORS["error"]
        status_suffix = "error"
    else:
        border_color = UI_COLORS["accent"]
        title_color = UI_COLORS["accent"]
        status_suffix = "done"

    return Panel(
        content,
        title=f"[{title_color}]research_codebase[/] [{status_suffix}]",
        subtitle=f"[{UI_COLORS['muted']}]{timestamp}[/]",
        border_style=Style(color=border_color),
        padding=(0, 1),
        expand=False,
    )
