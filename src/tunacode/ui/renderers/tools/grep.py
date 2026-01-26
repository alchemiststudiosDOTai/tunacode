"""NeXTSTEP-style panel renderer for grep tool output.

Displays search results with syntax highlighting based on matched file types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES

from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    build_hook_params_prefix,
    tool_renderer,
)


@dataclass
class GrepData:
    """Parsed grep result for structured display."""

    pattern: str
    total_matches: int
    strategy: str
    candidates: int
    matches: list[dict[str, Any]]
    is_truncated: bool
    case_sensitive: bool
    use_regex: bool
    context_lines: int


class GrepRenderer(BaseToolRenderer[GrepData]):
    """Renderer for grep tool output."""

    def parse_result(self, args: dict[str, Any] | None, result: str) -> GrepData | None:
        """Extract structured data from grep output.

        Expected format:
            Found N matches for pattern: <pattern>
            Strategy: <strategy> | Candidates: <N> files | ...
            <matches>
        """
        if not result or "Found" not in result:
            return None

        lines = result.strip().splitlines()
        if len(lines) < 2:
            return None

        # Parse header: "Found N match(es) for pattern: <pattern>"
        header_match = re.match(r"Found (\d+) match(?:es)? for pattern: (.+)", lines[0])
        if not header_match:
            return None

        total_matches = int(header_match.group(1))
        pattern = header_match.group(2).strip()

        # Parse strategy line
        strategy = "smart"
        candidates = 0
        if len(lines) > 1 and lines[1].startswith("Strategy:"):
            strat_match = re.match(r"Strategy: (\w+) \| Candidates: (\d+)", lines[1])
            if strat_match:
                strategy = strat_match.group(1)
                candidates = int(strat_match.group(2))

        # Parse matches
        matches: list[dict[str, Any]] = []
        current_file: str | None = None
        file_pattern = re.compile(r"\U0001f4c1 (.+?):(\d+)")
        match_pattern = re.compile(r"\u25b6\s*(\d+)\u2502\s*(.*?)\u27e8(.+?)\u27e9(.*)")

        for line in lines:
            file_match = file_pattern.search(line)
            if file_match:
                current_file = file_match.group(1)
                continue

            match_line = match_pattern.search(line)
            if match_line and current_file:
                line_num = int(match_line.group(1))
                before = match_line.group(2)
                match_text = match_line.group(3)
                after = match_line.group(4)

                matches.append(
                    {
                        "file": current_file,
                        "line": line_num,
                        "before": before,
                        "match": match_text,
                        "after": after,
                    }
                )

        if not matches and total_matches == 0:
            return None

        args = args or {}
        return GrepData(
            pattern=pattern,
            total_matches=total_matches,
            strategy=strategy,
            candidates=candidates,
            matches=matches,
            is_truncated=len(matches) < total_matches,
            case_sensitive=args.get("case_sensitive", False),
            use_regex=args.get("use_regex", False),
            context_lines=args.get("context_lines", 2),
        )

    def build_header(
        self,
        data: GrepData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 1: Pattern + match count."""
        header = Text()
        header.append(f'"{data.pattern}"', style="bold")
        match_word = "match" if data.total_matches == 1 else "matches"
        header.append(f"   {data.total_matches} {match_word}", style="dim")
        return header

    def build_params(self, data: GrepData, max_line_width: int) -> Text:
        """Zone 2: Parameters (strategy, case, regex, context)."""
        case_val = "yes" if data.case_sensitive else "no"
        regex_val = "yes" if data.use_regex else "no"
        params = build_hook_params_prefix()
        params.append("strategy:", style="dim")
        params.append(f" {data.strategy}", style="dim bold")
        params.append("  case:", style="dim")
        params.append(f" {case_val}", style="dim bold")
        params.append("  regex:", style="dim")
        params.append(f" {regex_val}", style="dim bold")
        params.append("  context:", style="dim")
        params.append(f" {data.context_lines}", style="dim bold")
        return params

    def build_viewport(self, data: GrepData, max_line_width: int) -> RenderableType:
        """Zone 3: Matches viewport with styled file paths and highlighted matches."""
        if not data.matches:
            return Text("(no matches)", style="dim italic")

        viewport_parts: list[RenderableType] = []
        current_file: str | None = None
        lines_used = 0
        max_lines = TOOL_VIEWPORT_LINES

        for match in data.matches:
            if lines_used >= max_lines:
                break

            # File header when switching files
            if match["file"] != current_file:
                if current_file is not None and lines_used < max_lines:
                    viewport_parts.append(Text(""))
                    lines_used += 1

                current_file = match["file"]
                if lines_used < max_lines:
                    indent = "  "
                    file_header = Text()
                    file_header.append(indent, style="")
                    file_header.append(current_file, style="cyan bold")
                    viewport_parts.append(file_header)
                    lines_used += 1

            if lines_used >= max_lines:
                break

            # Match line with highlighted match text
            prefix = f"    {match['line']:>4}│ "
            match_line = Text()
            match_line.append(prefix, style="dim")

            # Render full content and let Rich wrap at render width
            before = match["before"]
            match_text = match["match"]
            after = match["after"]
            match_line.append(before, style="")
            match_line.append(match_text, style="bold yellow reverse")
            match_line.append(after, style="")

            viewport_parts.append(match_line)
            lines_used += 1

        # Pad to minimum height
        while lines_used < MIN_VIEWPORT_LINES:
            viewport_parts.append(Text(""))
            lines_used += 1

        return Group(*viewport_parts)

    def build_status(
        self,
        data: GrepData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 4: Status with truncation info and timing."""
        status_items: list[str] = []
        if data.is_truncated:
            status_items.append(f"[{len(data.matches)}/{data.total_matches} shown]")
        if data.candidates > 0:
            status_items.append(f"{data.candidates} files searched")
        if duration_ms is not None:
            status_items.append(f"{duration_ms:.0f}ms")

        return Text("  ".join(status_items), style="dim") if status_items else Text("")


# Module-level renderer instance
_renderer = GrepRenderer(RendererConfig(tool_name="grep"))


@tool_renderer("grep")
def render_grep(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None,
    max_line_width: int,
) -> RenderableType | None:
    """Render grep with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms, max_line_width)
