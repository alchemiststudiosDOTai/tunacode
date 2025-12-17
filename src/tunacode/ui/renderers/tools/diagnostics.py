"""NeXTSTEP-style renderer for LSP diagnostics."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import UI_COLORS
from tunacode.lsp.diagnostics import truncate_diagnostic_message

MAX_DIAGNOSTICS_DISPLAY = 10

BOX_HORIZONTAL = "\u2500"
SEPARATOR_WIDTH = 52


@dataclass
class DiagnosticItem:
    """A single diagnostic for display."""

    severity: str  # "error", "warning", "info", "hint"
    line: int
    message: str


@dataclass
class DiagnosticsData:
    """Parsed diagnostics for structured display."""

    items: list[DiagnosticItem]
    error_count: int
    warning_count: int
    info_count: int


def parse_diagnostics_block(content: str) -> DiagnosticsData | None:
    """Extract diagnostics from <file_diagnostics> XML block.

    Expected format:
        <file_diagnostics>
        Error (line 10): message text
        Warning (line 15): another message
        </file_diagnostics>
    """
    if not content:
        return None

    # Extract content between tags
    match = re.search(r"<file_diagnostics>(.*?)</file_diagnostics>", content, re.DOTALL)
    if not match:
        return None

    block_content = match.group(1).strip()
    if not block_content:
        return None

    items: list[DiagnosticItem] = []
    error_count = 0
    warning_count = 0
    info_count = 0

    # Parse each diagnostic line
    # Format: "Error (line 10): message" or "Warning (line 15): message"
    pattern = re.compile(r"^(Error|Warning|Info|Hint)\s+\(line\s+(\d+)\):\s*(.+)$", re.IGNORECASE)

    for line in block_content.splitlines():
        line = line.strip()
        if not line or line.startswith("Summary:"):
            continue

        match = pattern.match(line)
        if match:
            severity = match.group(1).lower()
            line_num = int(match.group(2))
            message = match.group(3)

            items.append(
                DiagnosticItem(
                    severity=severity,
                    line=line_num,
                    message=message,
                )
            )

            if severity == "error":
                error_count += 1
            elif severity == "warning":
                warning_count += 1
            else:
                info_count += 1

    if not items:
        return None

    return DiagnosticsData(
        items=items,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
    )


def render_diagnostics_inline(data: DiagnosticsData) -> RenderableType:
    """Render diagnostics as inline zone within update_file panel.

    NeXTSTEP 4-Zone Layout:
    +----------------------------------+
    | HEADER: 2 errors, 1 warning      |  <- color-coded counts
    +----------------------------------+
    | VIEWPORT:                        |
    |   L170: Type mismatch...         |  <- red
    |   L336: Argument type...         |  <- red
    |   L42:  Unused import            |  <- yellow
    +----------------------------------+
    """
    content_parts: list[RenderableType] = []

    # Zone 1: Header - counts with color coding
    header = Text()
    header.append("LSP Diagnostics", style="bold")
    header.append("  ", style="")

    if data.error_count > 0:
        error_suffix = "s" if data.error_count > 1 else ""
        header.append(f"{data.error_count} error{error_suffix}", style=UI_COLORS["error"])
        if data.warning_count > 0 or data.info_count > 0:
            header.append(", ", style="")

    if data.warning_count > 0:
        warning_suffix = "s" if data.warning_count > 1 else ""
        header.append(f"{data.warning_count} warning{warning_suffix}", style=UI_COLORS["warning"])
        if data.info_count > 0:
            header.append(", ", style="")

    if data.info_count > 0:
        header.append(f"{data.info_count} info", style=UI_COLORS["muted"])

    content_parts.append(header)
    content_parts.append(Text("\n"))

    separator = Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")
    content_parts.append(separator)
    content_parts.append(Text("\n"))

    # Zone 2: Viewport - diagnostic list
    for idx, item in enumerate(data.items):
        if idx >= MAX_DIAGNOSTICS_DISPLAY:
            remaining = len(data.items) - idx
            content_parts.append(Text(f"  +{remaining} more...", style="dim italic"))
            content_parts.append(Text("\n"))
            break

        # Severity color
        severity_style = UI_COLORS["error"] if item.severity == "error" else UI_COLORS["warning"]
        if item.severity in ("info", "hint"):
            severity_style = UI_COLORS["muted"]

        line_text = Text()
        line_text.append(f"  L{item.line:<4}", style="dim")
        line_text.append(truncate_diagnostic_message(item.message), style=severity_style)
        content_parts.append(line_text)
        content_parts.append(Text("\n"))

    return Group(*content_parts)


def extract_diagnostics_from_result(result: str) -> tuple[str, str | None]:
    """Extract and remove diagnostics block from tool result.

    Returns:
        Tuple of (result_without_diagnostics, diagnostics_block_or_none)
    """
    if "<file_diagnostics>" not in result:
        return result, None

    match = re.search(r"<file_diagnostics>.*?</file_diagnostics>", result, re.DOTALL)
    if not match:
        return result, None

    diagnostics_block = match.group(0)
    result_without = result.replace(diagnostics_block, "").strip()

    return result_without, diagnostics_block
