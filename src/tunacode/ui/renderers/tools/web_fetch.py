"""NeXTSTEP-style panel renderer for web_fetch tool output."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

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
class WebFetchData:
    """Parsed web_fetch result for structured display."""

    url: str
    domain: str
    content: str
    content_lines: int
    is_truncated: bool
    timeout: int


def parse_result(args: dict[str, Any] | None, result: str) -> WebFetchData | None:
    """Extract structured data from web_fetch output.

    The result is simply the text content from the fetched page.
    """
    if not result:
        return None

    args = args or {}
    url = args.get("url", "")
    timeout = args.get("timeout", 60)

    # Extract domain from URL
    domain = ""
    if url:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.hostname or ""
        except Exception:
            domain = url[:30]

    # Check for truncation
    is_truncated = "[Content truncated due to size]" in result

    content_lines = len(result.splitlines())

    return WebFetchData(
        url=url,
        domain=domain,
        content=result,
        content_lines=content_lines,
        is_truncated=is_truncated,
        timeout=timeout,
    )


def _truncate_line(line: str) -> str:
    """Truncate a single line if too wide."""
    if len(line) > MAX_PANEL_LINE_WIDTH:
        return line[: MAX_PANEL_LINE_WIDTH - 3] + "..."
    return line


def _truncate_content(content: str) -> tuple[str, int, int]:
    """Truncate content, return (truncated, shown, total)."""
    lines = content.splitlines()
    total = len(lines)

    max_lines = TOOL_VIEWPORT_LINES

    if total <= max_lines:
        return "\n".join(_truncate_line(ln) for ln in lines), total, total

    truncated = [_truncate_line(ln) for ln in lines[:max_lines]]
    return "\n".join(truncated), max_lines, total


def render_web_fetch(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render web_fetch with NeXTSTEP zoned layout.

    Zones:
    - Header: domain + content summary
    - Selection context: full URL, timeout
    - Primary viewport: content preview
    - Status: truncation info, duration
    """
    data = parse_result(args, result)
    if not data:
        return None

    # Zone 1: Domain + content summary
    header = Text()
    header.append(data.domain or "web", style="bold")
    header.append(f"   {data.content_lines} lines", style="dim")

    # Zone 2: Full URL + parameters
    params = Text()
    url_display = data.url
    if len(url_display) > 70:
        url_display = url_display[:67] + "..."
    params.append("url:", style="dim")
    params.append(f" {url_display}", style="dim bold")
    params.append("\n", style="")
    params.append("timeout:", style="dim")
    params.append(f" {data.timeout}s", style="dim bold")

    separator = Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")

    # Zone 3: Content viewport
    truncated_content, shown, total = _truncate_content(data.content)

    # Pad viewport to minimum height for visual consistency
    content_lines = truncated_content.split("\n")
    while len(content_lines) < MIN_VIEWPORT_LINES:
        content_lines.append("")
    truncated_content = "\n".join(content_lines)

    viewport = Text(truncated_content)

    # Zone 4: Status
    status_items: list[str] = []

    if data.is_truncated:
        status_items.append("(content truncated)")

    if shown < total:
        status_items.append(f"[{shown}/{total} lines]")

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
        title=f"[{UI_COLORS['success']}]web_fetch[/] [done]",
        subtitle=f"[{UI_COLORS['muted']}]{timestamp}[/]",
        border_style=Style(color=UI_COLORS["success"]),
        padding=(0, 1),
        expand=False,
    )
