"""NeXTSTEP-style panel renderer for discover tool output.

Displays code discovery results with clusters, relevance markers, and file tree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES

from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    ToolRenderResult,
    build_hook_params_prefix,
    tool_renderer,
)


class Relevance(Enum):
    HIGH = "high"
    MEDIUM = "medium"


@dataclass
class DiscoverFile:
    """A single discovered file entry."""

    path: str
    relevance: Relevance
    role: str
    key_symbols: list[str]
    imports_from: list[str]
    line_count: int
    excerpt: str


@dataclass
class DiscoverCluster:
    """A group of files implementing a concept."""

    name: str
    description: str
    files: list[DiscoverFile]


@dataclass
class DiscoverData:
    """Parsed discover result for structured display."""

    query: str
    summary: str
    clusters: list[DiscoverCluster]
    file_tree: str
    total_files_scanned: int
    total_candidates: int
    overflow_dirs: list[str]


class DiscoverRenderer(BaseToolRenderer[DiscoverData]):
    """Renderer for discover tool output."""

    def _parse_cluster_section(self, section: str) -> DiscoverCluster | None:
        """Parse a single ## cluster section into a DiscoverCluster."""
        section_lines = section.splitlines()
        if not section_lines:
            return None

        cluster_name = section_lines[0].strip()
        cluster_description = section_lines[1].strip() if len(section_lines) > 1 else ""

        files = self._parse_file_entries(section_lines[2:])
        if not files:
            return None

        return DiscoverCluster(
            name=cluster_name,
            description=cluster_description,
            files=files,
        )

    def _parse_file_entries(self, lines: list[str]) -> list[DiscoverFile]:
        """Parse file entry lines into DiscoverFile objects."""
        files: list[DiscoverFile] = []
        current_path = ""
        current_relevance = Relevance.MEDIUM
        current_role = ""
        current_symbols: list[str] = []
        current_imports: list[str] = []
        current_line_count = 0
        current_excerpt = ""

        file_pattern = re.compile(r"([★◆])\s+`(.+?)`\s+—\s+(.+?)\s+\((\d+)L\)")

        for raw_line in lines:
            line = raw_line.strip()

            match = file_pattern.match(line)
            if match:
                if current_path:
                    files.append(
                        DiscoverFile(
                            path=current_path,
                            relevance=current_relevance,
                            role=current_role,
                            key_symbols=current_symbols.copy(),
                            imports_from=current_imports.copy(),
                            line_count=current_line_count,
                            excerpt=current_excerpt,
                        )
                    )

                marker = match.group(1)
                current_path = match.group(2)
                current_relevance = Relevance.HIGH if marker == "★" else Relevance.MEDIUM
                current_role = match.group(3)
                current_line_count = int(match.group(4))
                current_symbols = []
                current_imports = []
                current_excerpt = ""
                continue

            if line.startswith("defines:"):
                symbols_str = line[len("defines:") :].strip()
                current_symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
            elif line.startswith("imports:"):
                imports_str = line[len("imports:") :].strip()
                current_imports = [s.strip() for s in imports_str.split(",") if s.strip()]
            elif line.startswith("context:"):
                current_excerpt = line[len("context:") :].strip()

        if current_path:
            files.append(
                DiscoverFile(
                    path=current_path,
                    relevance=current_relevance,
                    role=current_role,
                    key_symbols=current_symbols,
                    imports_from=current_imports,
                    line_count=current_line_count,
                    excerpt=current_excerpt,
                )
            )

        return files

    @staticmethod
    def _find_summary(lines: list[str]) -> str:
        """Find summary line after the query header."""
        non_content_prefixes = ("(", "```", "##")
        for line in lines[1:]:
            stripped = line.strip()
            if stripped and not any(stripped.startswith(p) for p in non_content_prefixes):
                return stripped
        return ""

    def parse_result(self, args: dict[str, Any] | None, result: str) -> DiscoverData | None:
        """Parse discover output into structured data."""
        if not result:
            return None

        lines = result.strip().splitlines()
        if not lines:
            return None

        query = ""
        if lines[0].startswith("# Discovery:"):
            query = lines[0][len("# Discovery:") :].strip()

        scanned_match = re.search(r"\((\d+) scanned → (\d+) relevant\)", result)
        total_scanned = int(scanned_match.group(1)) if scanned_match else 0
        total_candidates = int(scanned_match.group(2)) if scanned_match else 0

        summary = self._find_summary(lines)

        file_tree = ""
        tree_match = re.search(r"```\n(.*?)```", result, re.DOTALL)
        if tree_match:
            file_tree = tree_match.group(1).strip()

        clusters: list[DiscoverCluster] = []
        for section in re.split(r"\n## ", result)[1:]:
            if not section.strip():
                continue
            cluster = self._parse_cluster_section(section)
            if cluster:
                clusters.append(cluster)

        overflow_match = re.search(r"\(\+(\d+) more in: (.+)\)", result)
        overflow_dirs: list[str] = []
        if overflow_match:
            overflow_dirs = [s.strip() for s in overflow_match.group(2).split(",")]

        return DiscoverData(
            query=query,
            summary=summary,
            clusters=clusters,
            file_tree=file_tree,
            total_files_scanned=total_scanned,
            total_candidates=total_candidates,
            overflow_dirs=overflow_dirs,
        )

    def build_header(
        self,
        data: DiscoverData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 1: Query + summary."""
        header = Text()
        header.append(f'"{data.query}"', style="bold")
        if data.summary:
            # Extract key stats from summary
            summary_short = data.summary.split(".")[0] if "." in data.summary else data.summary
            header.append(f"   {summary_short}", style="dim")
        return header

    def build_params(self, data: DiscoverData, max_line_width: int) -> Text | None:
        """Zone 2: Scan stats."""
        params = build_hook_params_prefix()
        params.append("scanned:", style="dim")
        params.append(f" {data.total_files_scanned}", style="dim bold")
        params.append("  found:", style="dim")
        params.append(f" {data.total_candidates}", style="dim bold")
        params.append("  areas:", style="dim")
        params.append(f" {len(data.clusters)}", style="dim bold")
        return params

    def _render_file_entry(
        self,
        file_entry: DiscoverFile,
        parts: list[RenderableType],
        lines_used: int,
        max_display: int,
    ) -> int:
        """Render a single file entry, returning updated lines_used count."""
        marker = "★" if file_entry.relevance == Relevance.HIGH else "◆"
        style = "bright_green" if file_entry.relevance == Relevance.HIGH else "yellow"

        file_line = Text()
        file_line.append(f"  {marker} ", style=style)
        file_line.append(file_entry.path, style="bold")
        if file_entry.role:
            file_line.append(f" — {file_entry.role}", style="dim")
        file_line.append(f" ({file_entry.line_count}L)", style="dim")
        parts.append(file_line)
        lines_used += 1

        if file_entry.key_symbols and lines_used < max_display:
            symbols_line = Text()
            symbols_line.append("    defines: ", style="dim")
            symbols_line.append(", ".join(file_entry.key_symbols[:4]), style="cyan")
            parts.append(symbols_line)
            lines_used += 1

        if file_entry.excerpt and lines_used < max_display:
            excerpt_line = Text()
            excerpt_line.append("    context: ", style="dim")
            max_excerpt_len = 80
            excerpt = (
                file_entry.excerpt[:max_excerpt_len] + "..."
                if len(file_entry.excerpt) > max_excerpt_len
                else file_entry.excerpt
            )
            excerpt_line.append(excerpt, style="italic")
            parts.append(excerpt_line)
            lines_used += 1

        return lines_used

    def build_viewport(self, data: DiscoverData, max_line_width: int) -> RenderableType:
        """Zone 3: Discovery results viewport."""
        if not data.clusters:
            return Text("(no results)", style="dim italic")

        viewport_parts: list[RenderableType] = []
        lines_used = 0
        max_display = TOOL_VIEWPORT_LINES

        for cluster in data.clusters:
            if lines_used >= max_display:
                break

            cluster_line = Text()
            cluster_line.append(f"## {cluster.name}", style="bold cyan")
            viewport_parts.append(cluster_line)
            lines_used += 1

            if lines_used >= max_display:
                break

            desc_line = Text(cluster.description, style="dim")
            viewport_parts.append(desc_line)
            lines_used += 1

            for file_entry in cluster.files:
                if lines_used >= max_display:
                    break
                lines_used = self._render_file_entry(
                    file_entry, viewport_parts, lines_used, max_display
                )

            if lines_used < max_display:
                viewport_parts.append(Text(""))
                lines_used += 1

        while lines_used < MIN_VIEWPORT_LINES:
            viewport_parts.append(Text(""))
            lines_used += 1

        return Group(*viewport_parts)

    def build_status(
        self,
        data: DiscoverData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 4: Status with overflow info and timing."""
        status_items: list[str] = []

        if data.overflow_dirs:
            status_items.append(f"+{len(data.overflow_dirs)} more")

        if data.file_tree:
            status_items.append("tree")

        if duration_ms is not None:
            status_items.append(f"{duration_ms:.0f}ms")

        return Text("  ".join(status_items), style="dim") if status_items else Text("")


# Module-level renderer instance
_renderer = DiscoverRenderer(RendererConfig(tool_name="discover"))


@tool_renderer("discover")
def render_discover(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None,
    max_line_width: int,
) -> ToolRenderResult:
    """Render discover with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms, max_line_width)
