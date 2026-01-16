"""Slim NeXTSTEP-style panel renderer for web_fetch tool output.

Dream mockup style:
─ web_fetch ────────────────────────────── 200 OK
  ↳ https://api.example.com/v1/users

{
  "users": [
    {"id": 1, "name": "Alice"},
    ...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from rich.console import RenderableType
from rich.text import Text

from tunacode.constants import MIN_VIEWPORT_LINES, URL_DISPLAY_MAX_LENGTH
from tunacode.ui.renderers.tools.base import tool_renderer, truncate_content
from tunacode.ui.renderers.tools.slim_base import slim_footer, slim_panel
from tunacode.ui.renderers.tools.syntax_utils import detect_code_lexer, syntax_or_text


@dataclass
class WebFetchData:
    """Parsed web_fetch result for structured display."""

    url: str
    domain: str
    content: str
    content_lines: int
    is_truncated: bool
    timeout: int


def parse_web_fetch_result(
    args: dict[str, Any] | None, result: str
) -> WebFetchData | None:
    """Extract structured data from web_fetch output."""
    if not result:
        return None

    args = args or {}
    url = args.get("url", "")
    timeout = args.get("timeout", 60)

    domain = ""
    if url:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.hostname or ""
        except Exception:
            domain = url[:30]

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


def _detect_content_type(url: str, content: str) -> str | None:
    """Detect content type from URL or content."""
    url_lower = url.lower()

    is_json_url = ".json" in url_lower or "/api/" in url_lower
    if is_json_url and content.strip().startswith(("{", "[")):
        return "json"

    is_xml_url = ".xml" in url_lower or "rss" in url_lower or "atom" in url_lower
    if is_xml_url and content.strip().startswith("<"):
        return "xml"

    if ".yaml" in url_lower or ".yml" in url_lower:
        return "yaml"

    if "raw.githubusercontent.com" in url_lower:
        if ".py" in url_lower:
            return "python"
        if ".js" in url_lower:
            return "javascript"
        if ".ts" in url_lower:
            return "typescript"
        if ".rs" in url_lower:
            return "rust"
        if ".go" in url_lower:
            return "go"

    return detect_code_lexer(content)


@tool_renderer("web_fetch")
def render_web_fetch(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render web_fetch with slim NeXTSTEP panel style.

    Dream mockup format:
    ─ web_fetch ─────────────────────────── 200 OK
      ↳ https://api.example.com/v1/users

    {
      "users": [...]
    }
    """
    data = parse_web_fetch_result(args, result)
    if data is None:
        return None

    # Build stats
    stats = f"{data.content_lines} lines"

    # Subtitle: URL (truncated if needed)
    url_display = data.url
    if len(url_display) > URL_DISPLAY_MAX_LENGTH:
        url_display = url_display[: URL_DISPLAY_MAX_LENGTH - 3] + "..."

    # Build viewport
    if not data.content:
        viewport = Text("(no content)", style="dim italic")
    else:
        truncated_content, shown, total = truncate_content(data.content)

        lexer = _detect_content_type(data.url, data.content)

        if lexer:
            viewport = syntax_or_text(truncated_content, lexer=lexer)
        else:
            content_lines = truncated_content.split("\n")
            while len(content_lines) < MIN_VIEWPORT_LINES:
                content_lines.append("")

            viewport = Text("\n".join(content_lines))

    # Footer
    _, shown, total = truncate_content(data.content)
    footer = slim_footer(shown, total)

    return slim_panel(
        name="web_fetch",
        content=viewport,
        stats=stats,
        subtitle=url_display,
        footer=footer if str(footer) else None,
    )
