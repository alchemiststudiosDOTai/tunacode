"""Slim NeXTSTEP-style panel renderer for grep tool output.

Dream mockup style:
- grep ----- 15 matches - 8 files
  > pattern: "BaseToolRenderer"

  src/tunacode/ui/renderers/tools/base.py
    244| class BaseToolRenderer(ABC, Generic[T]):
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES
from tunacode.ui.renderers.tools.base import tool_renderer, truncate_line
from tunacode.ui.renderers.tools.slim_base import slim_footer, slim_panel


@dataclass
class GrepData:
    """Parsed grep result for structured display."""

    pattern: str
    total_matches: int
    strategy: str
    candidates: int
    matches: list[dict[str, Any]]
    is_truncated: bool


def parse_grep_result(args: dict[str, Any] | None, result: str) -> GrepData | None:
    """Extract structured data from grep output."""
    if not result:
        return None

    lines = result.strip().splitlines()
    if not lines:
        return None

    # Try to find pattern and match count from various formats
    total_matches = 0
    pattern = ""

    # Format 1: "Found X match(es) for pattern: Y"
    header_match = re.match(r"Found (\d+) match(?:es)? for pattern: (.+)", lines[0])
    if header_match:
        total_matches = int(header_match.group(1))
        pattern = header_match.group(2).strip()
    else:
        # Format 2: "No matches found for pattern: Y"
        no_match = re.match(r"No matches found for pattern: (.+)", lines[0])
        if no_match:
            total_matches = 0
            pattern = no_match.group(1).strip()
        else:
            return None

    strategy = "smart"
    candidates = 0
    for line in lines[1:4]:  # Check first few lines for strategy
        if line.startswith("Strategy:"):
            # Format 1: "Strategy: X | Candidates: Y"
            strat_match = re.match(r"Strategy: (\w+) \| Candidates: (\d+)", line)
            if strat_match:
                strategy = strat_match.group(1)
                candidates = int(strat_match.group(2))
            else:
                # Format 2: "Strategy: X (was Y), Files: N/M"
                strat_re = r"Strategy: (\w+)(?: \(was \w+\))?, Files: (\d+)/(\d+)"
                strat_match2 = re.match(strat_re, line)
                if strat_match2:
                    strategy = strat_match2.group(1)
                    candidates = int(strat_match2.group(2))
            break

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

    return GrepData(
        pattern=pattern,
        total_matches=total_matches,
        strategy=strategy,
        candidates=candidates,
        matches=matches,
        is_truncated=len(matches) < total_matches,
    )


@tool_renderer("grep")
def render_grep(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render grep with slim NeXTSTEP panel style.

    Dream mockup format:
    ─ grep ─────────────────────── 15 matches · 8 files
      ↳ pattern: "BaseToolRenderer"

      src/tunacode/ui/renderers/tools/base.py
        244│ class BaseToolRenderer(ABC, Generic[T]):
    """
    data = parse_grep_result(args, result)
    if data is None:
        return None

    # Build stats
    match_word = "match" if data.total_matches == 1 else "matches"
    stats = f"{data.total_matches} {match_word}"
    if data.candidates > 0:
        stats += f" · {data.candidates} files"

    # Subtitle text
    subtitle_text = f'pattern: "{data.pattern}"'

    # Build viewport
    if not data.matches:
        viewport = Text("(no matches)", style="dim italic")
    else:
        viewport_parts: list[RenderableType] = []
        current_file: str | None = None
        lines_used = 0
        max_lines = TOOL_VIEWPORT_LINES

        for match in data.matches:
            if lines_used >= max_lines:
                break

            if match["file"] != current_file:
                if current_file is not None and lines_used < max_lines:
                    viewport_parts.append(Text(""))
                    lines_used += 1

                current_file = match["file"]
                if lines_used < max_lines:
                    file_header = Text()
                    file_header.append("  ", style="")
                    file_header.append(current_file, style="cyan bold")
                    viewport_parts.append(file_header)
                    lines_used += 1

            if lines_used >= max_lines:
                break

            match_line = Text()
            match_line.append(f"    {match['line']:>4}", style="dim")
            match_line.append("│ ", style="dim")

            before = match["before"]
            match_text = match["match"]
            after = match["after"]
            full_line = f"{before}{match_text}{after}"
            truncated = truncate_line(full_line, max_width=60)

            if truncated == full_line:
                match_line.append(before, style="")
                match_line.append(match_text, style="bold yellow reverse")
                match_line.append(after, style="")
            else:
                match_line.append(truncated, style="")

            viewport_parts.append(match_line)
            lines_used += 1

        while lines_used < MIN_VIEWPORT_LINES:
            viewport_parts.append(Text(""))
            lines_used += 1

        viewport = Group(*viewport_parts)

    # Footer
    footer = slim_footer(len(data.matches), data.total_matches)

    return slim_panel(
        name="grep",
        content=viewport,
        stats=stats,
        subtitle=subtitle_text,
        footer=footer if str(footer) else None,
    )
