"""NeXTSTEP-style panel renderer for research_codebase tool output."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from rich.console import RenderableType
from rich.text import Text

from tunacode.constants import (
    MIN_VIEWPORT_LINES,
    TOOL_VIEWPORT_LINES,
    UI_COLORS,
)
from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    tool_renderer,
    truncate_line,
)


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


class ResearchRenderer(BaseToolRenderer[ResearchData]):
    """Renderer for research_codebase tool output with multi-section viewport."""

    def _parse_dict_result(self, result: str) -> dict[str, Any] | None:
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

    def parse_result(self, args: dict[str, Any] | None, result: str) -> ResearchData | None:
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
        directories = args.get("directories", ["."])
        max_files = args.get("max_files", 3)

        if isinstance(directories, str):
            directories = [directories]

        parsed = self._parse_dict_result(result)
        if not parsed:
            # Could not parse - return error state with raw result as finding
            return ResearchData(
                query=query,
                directories=directories,
                max_files=max_files,
                key_findings=[result[:500] if result else "No results"],
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

    def build_header(self, data: ResearchData, duration_ms: float | None) -> Text:
        """Zone 1: Query summary."""
        header = Text()
        header.append("Query: ", style="dim")
        max_query_display_length = 60
        query_too_long = len(data.query) > max_query_display_length
        query_display = (
            data.query[:max_query_display_length] + "..." if query_too_long else data.query
        )
        header.append(f'"{query_display}"', style="bold")
        return header

    def build_params(self, data: ResearchData) -> Text:
        """Zone 2: Parameters (directories, max_files)."""
        max_directories_display = 3
        dirs_display = ", ".join(data.directories[:max_directories_display])
        if len(data.directories) > max_directories_display:
            dirs_display += f" (+{len(data.directories) - max_directories_display})"

        params = Text()
        params.append("dirs:", style="dim")
        params.append(f" {dirs_display}", style="dim bold")
        params.append("  max_files:", style="dim")
        params.append(f" {data.max_files}", style="dim bold")
        return params

    def build_viewport(self, data: ResearchData) -> RenderableType:
        """Zone 3: Multi-section viewport (files, findings, recommendations)."""

        viewport_lines: list[Text] = []
        lines_used = 0
        max_viewport_lines = TOOL_VIEWPORT_LINES
        min_lines_for_recommendations = 2

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
                file_line.append(truncate_line(filepath), style="cyan")
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
                finding_text = truncate_line(finding)
                finding_line.append(finding_text)
                viewport_lines.append(finding_line)
                lines_used += 1

            viewport_lines.append(Text(""))
            lines_used += 1

        # Recommendations section (if space)
        if data.recommendations and lines_used < max_viewport_lines - min_lines_for_recommendations:
            rec_header = Text()
            rec_header.append("Recommendations", style="bold")
            viewport_lines.append(rec_header)
            lines_used += 1

            for rec in data.recommendations:
                if lines_used >= max_viewport_lines:
                    break
                rec_line = Text()
                rec_line.append("  > ", style="dim")
                rec_line.append(truncate_line(rec), style="italic")
                viewport_lines.append(rec_line)
                lines_used += 1

        # Pad viewport to minimum height
        while lines_used < MIN_VIEWPORT_LINES:
            viewport_lines.append(Text(""))
            lines_used += 1

        return Text("\n").join(viewport_lines) if viewport_lines else Text("(no findings)")

    def build_status(self, data: ResearchData, duration_ms: float | None) -> Text:
        """Zone 4: Status with file count, findings count, timing."""
        status_items: list[str] = []
        status_items.append(f"files: {len(data.relevant_files)}")
        status_items.append(f"findings: {len(data.key_findings)}")
        if duration_ms is not None:
            status_items.append(f"{duration_ms:.0f}ms")

        return Text("  ".join(status_items), style="dim")

    def get_border_color(self, data: ResearchData) -> str:
        """Use error color if error occurred, otherwise accent color."""
        if data.is_error:
            return UI_COLORS["error"]
        return UI_COLORS["accent"]

    def get_status_text(self, data: ResearchData) -> str:
        """Return 'error' if error occurred, otherwise 'done'."""
        if data.is_error:
            return "error"
        return "done"


# Module-level renderer instance
_renderer = ResearchRenderer(RendererConfig(tool_name="research_codebase"))


@tool_renderer("research_codebase")
def render_research_codebase(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render research_codebase with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms)
