"""Agent response renderer following NeXTSTEP panel pattern.

Renders finalized agent text responses in a styled panel.
Uses accent (pink) border color for visual consistency.

Layout:
- Title bar: "agent" label + timestamp
- Viewport: markdown content
- Status: throughput
"""

from __future__ import annotations

from datetime import datetime

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.text import Text

from tunacode.core.ui_api.constants import (
    BOX_HORIZONTAL,
    SEPARATOR_WIDTH,
    UI_COLORS,
)

from tunacode.ui.widgets.chat import PanelMeta

# Threshold for k-suffix (tokens) and ms->s conversion (duration)
UNIT_CONVERSION_THRESHOLD = 1000


def _format_tokens(tokens: int) -> str:
    """Format token count with k suffix for readability.

    Precondition: tokens >= 0
    """
    if tokens < 0:
        raise ValueError(f"Token count must be non-negative, got {tokens}")
    if tokens >= UNIT_CONVERSION_THRESHOLD:
        return f"{tokens / UNIT_CONVERSION_THRESHOLD:.1f}k"
    return f"{tokens}"


def _format_duration(duration_ms: float) -> str:
    """Format duration in human-readable form.

    Precondition: duration_ms >= 0
    """
    if duration_ms < 0:
        raise ValueError(f"Duration must be non-negative, got {duration_ms}")
    if duration_ms >= UNIT_CONVERSION_THRESHOLD:
        return f"{duration_ms / UNIT_CONVERSION_THRESHOLD:.1f}s"
    return f"{duration_ms:.0f}ms"


def _build_separator() -> Text:
    """Build horizontal separator line."""
    return Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")


def render_agent_streaming(
    content: str,
    elapsed_ms: float = 0.0,
) -> tuple[RenderableType, PanelMeta]:
    """Render streaming agent response as content + panel metadata.

    Uses same 3-zone layout as finalized response but with
    visual indicators for active streaming state.

    Args:
        content: Current markdown content being streamed
        elapsed_ms: Time since streaming started

    Returns:
        Tuple of (Rich renderable, PanelMeta) for CSS-styled display.
    """
    if elapsed_ms < 0:
        raise ValueError(f"elapsed_ms must be non-negative, got {elapsed_ms}")

    border_color = UI_COLORS["primary"]  # Primary color for "running" state
    muted_color = UI_COLORS["muted"]

    # Viewport (markdown content)
    viewport = Markdown(content) if content else Text("...", style="dim italic")

    # Status bar - streaming indicator
    status_parts: list[str] = ["streaming"]
    if elapsed_ms > 0:
        status_parts.append(_format_duration(elapsed_ms))

    status = Text()
    status.append("  ·  ".join(status_parts), style=muted_color)

    separator = _build_separator()

    content_parts: list[RenderableType] = [
        viewport,
        Text("\n"),
        separator,
        Text("\n"),
        status,
    ]

    meta = PanelMeta(
        css_class="agent-panel",
        border_title=f"[{border_color}]agent[/] [...]",
    )

    return Group(*content_parts), meta


def render_agent_response(
    content: str,
    tokens: int = 0,
    duration_ms: float = 0.0,
) -> tuple[RenderableType, PanelMeta]:
    """Render agent response as content + panel metadata.

    Args:
        content: Markdown content from the agent
        tokens: Completion token count
        duration_ms: Request duration in milliseconds

    Returns:
        Tuple of (Rich renderable, PanelMeta) for CSS-styled display.
    """
    if tokens < 0:
        raise ValueError(f"tokens must be non-negative, got {tokens}")
    if duration_ms < 0:
        raise ValueError(f"duration_ms must be non-negative, got {duration_ms}")

    border_color = UI_COLORS["accent"]
    muted_color = UI_COLORS["muted"]
    timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")

    # Viewport (markdown content)
    viewport = Markdown(content)

    # Status bar
    status_parts: list[str] = []
    if tokens > 0 and duration_ms > 0:
        status_parts.append(f"{tokens * 1000 / duration_ms:.0f} t/s")

    status = Text()
    status.append("  ·  ".join(status_parts) if status_parts else "", style=muted_color)

    separator = _build_separator()

    # Compose: viewport + separator + status
    content_parts: list[RenderableType] = [
        viewport,
        Text("\n"),
        separator,
        Text("\n"),
        status,
    ]

    meta = PanelMeta(
        css_class="agent-panel",
        border_title=f"[{border_color}]agent[/]",
        border_subtitle=f"[{muted_color}]{timestamp}[/]",
    )

    return Group(*content_parts), meta
