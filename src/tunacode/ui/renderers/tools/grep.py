"""NeXTSTEP-style panel renderer for grep tool output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from tunacode.constants import (
    MAX_PANEL_LINE_WIDTH,
    MIN_VIEWPORT_LINES,
    TOOL_VIEWPORT_LINES,
    UI_COLORS,
)

BOX_HORIZONTAL = "\u2500"
SEPARATOR_WIDTH = 52


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


def parse_result(args: dict[str, Any] | None, result: str) -> GrepData | None:
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


def _truncate_line(line: str) -> str:
    """Truncate a single line if too wide."""
    if len(line) > MAX_PANEL_LINE_WIDTH:
        return line[: MAX_PANEL_LINE_WIDTH - 3] + "..."
    return line


def render_grep(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render grep with NeXTSTEP zoned layout.

    Zones:
    - Header: pattern + match count
    - Selection context: strategy, case, regex parameters
    - Primary viewport: grouped matches by file
    - Status: truncation info, duration
    """
    data = parse_result(args, result)
    if not data:
        return None

    # Zone 1: Pattern + counts
    header = Text()
    header.append(f'"{data.pattern}"', style="bold")
    match_word = "match" if data.total_matches == 1 else "matches"
    header.append(f"   {data.total_matches} {match_word}", style="dim")

    # Zone 2: Parameters
    case_val = "yes" if data.case_sensitive else "no"
    regex_val = "yes" if data.use_regex else "no"
    params = Text()
    params.append("strategy:", style="dim")
    params.append(f" {data.strategy}", style="dim bold")
    params.append("  case:", style="dim")
    params.append(f" {case_val}", style="dim bold")
    params.append("  regex:", style="dim")
    params.append(f" {regex_val}", style="dim bold")
    params.append("  context:", style="dim")
    params.append(f" {data.context_lines}", style="dim bold")

    separator = Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")

    # Zone 3: Matches viewport grouped by file
    viewport_lines: list[str] = []
    current_file: str | None = None
    shown_matches = 0

    for match in data.matches:
        if shown_matches >= TOOL_VIEWPORT_LINES:
            break

        if match["file"] != current_file:
            if current_file is not None:
                viewport_lines.append("")
                shown_matches += 1
            current_file = match["file"]
            viewport_lines.append(f"  {current_file}")
            shown_matches += 1

        line_content = f"    {match['line']:>4}| {match['before']}{match['match']}{match['after']}"
        viewport_lines.append(_truncate_line(line_content))
        shown_matches += 1

    # Pad viewport to minimum height for visual consistency
    while len(viewport_lines) < MIN_VIEWPORT_LINES:
        viewport_lines.append("")

    viewport = Text("\n".join(viewport_lines)) if viewport_lines else Text("(no matches)")

    # Zone 4: Status
    status_items: list[str] = []
    if data.is_truncated:
        status_items.append(f"[{len(data.matches)}/{data.total_matches} shown]")
    if data.candidates > 0:
        status_items.append(f"{data.candidates} files searched")
    if duration_ms is not None:
        status_items.append(f"{duration_ms:.0f}ms")

    status = Text("  ".join(status_items), style="dim") if status_items else Text("")

    # Compose
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

    return Panel(
        content,
        title=f"[{UI_COLORS['success']}]grep[/] [done]",
        subtitle=f"[{UI_COLORS['muted']}]{timestamp}[/]",
        border_style=Style(color=UI_COLORS["success"]),
        padding=(0, 1),
        expand=False,
    )
