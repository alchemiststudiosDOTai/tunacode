"""NeXTSTEP-style panel renderer for web_fetch tool output.

Displays fetched web content with smart syntax highlighting based on URL or content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from rich.console import RenderableType
from rich.text import Text

from tunacode.constants import MIN_VIEWPORT_LINES, URL_DISPLAY_MAX_LENGTH

from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    build_hook_params_prefix,
    tool_renderer,
    truncate_content,
)
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


class WebFetchRenderer(BaseToolRenderer[WebFetchData]):
    """Renderer for web_fetch tool output."""

    def parse_result(self, args: dict[str, Any] | None, result: str) -> WebFetchData | None:
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

    def build_header(
        self,
        data: WebFetchData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 1: Domain + content summary."""
        header = Text()
        header.append(data.domain or "web", style="bold")
        header.append(f"   {data.content_lines} lines", style="dim")
        return header

    def build_params(self, data: WebFetchData, max_line_width: int) -> Text:
        """Zone 2: Full URL + parameters."""
        params = build_hook_params_prefix()
        url_display = data.url
        if len(url_display) > URL_DISPLAY_MAX_LENGTH:
            url_display = url_display[: URL_DISPLAY_MAX_LENGTH - 3] + "..."
        params.append("url:", style="dim")
        params.append(f" {url_display}", style="dim bold")
        params.append("\n", style="")
        params.append("timeout:", style="dim")
        params.append(f" {data.timeout}s", style="dim bold")
        return params

    def _detect_content_type(self, url: str, content: str) -> str | None:
        """Detect content type from URL or content."""
        url_lower = url.lower()

        # URL-based detection
        is_json_url = ".json" in url_lower or "/api/" in url_lower
        if is_json_url and content.strip().startswith(("{", "[")):
            return "json"

        is_xml_url = ".xml" in url_lower or "rss" in url_lower or "atom" in url_lower
        if is_xml_url and content.strip().startswith("<"):
            return "xml"

        if ".yaml" in url_lower or ".yml" in url_lower:
            return "yaml"

        if "raw.githubusercontent.com" in url_lower:
            # Try to detect from path
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

        # Content-based detection
        return detect_code_lexer(content)

    def build_viewport(self, data: WebFetchData, max_line_width: int) -> RenderableType:
        """Zone 3: Content viewport with smart highlighting."""
        if not data.content:
            return Text("(no content)", style="dim italic")

        truncated_content, shown, total = truncate_content(
            data.content,
            max_width=max_line_width,
        )

        # Detect if content is code/structured data
        lexer = self._detect_content_type(data.url, data.content)

        if lexer:
            return syntax_or_text(truncated_content, lexer=lexer)

        # Pad viewport for plain text
        content_lines = truncated_content.split("\n")
        while len(content_lines) < MIN_VIEWPORT_LINES:
            content_lines.append("")

        return Text("\n".join(content_lines))

    def build_status(
        self,
        data: WebFetchData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 4: Status with truncation info and timing."""

        status_items: list[str] = []

        if data.is_truncated:
            status_items.append("(content truncated)")

        _, shown, total = truncate_content(data.content, max_width=max_line_width)
        if shown < total:
            status_items.append(f"[{shown}/{total} lines]")

        if duration_ms is not None:
            status_items.append(f"{duration_ms:.0f}ms")

        return Text("  ".join(status_items), style="dim") if status_items else Text("")


# Module-level renderer instance
_renderer = WebFetchRenderer(RendererConfig(tool_name="web_fetch"))


@tool_renderer("web_fetch")
def render_web_fetch(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None,
    max_line_width: int,
) -> RenderableType | None:
    """Render web_fetch with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms, max_line_width)
