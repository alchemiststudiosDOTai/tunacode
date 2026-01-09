"""Agent response renderer following NeXTSTEP panel pattern.

Renders finalized agent text responses in a styled panel.
Uses accent (pink) border color for visual consistency.

Layout:
- Title bar: "agent" label + timestamp
- Viewport: markdown content
- Status: tokens · duration · model
"""

from __future__ import annotations

from datetime import datetime

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from tunacode.constants import (
    BOX_HORIZONTAL,
    SEPARATOR_WIDTH,
    UI_COLORS,
)


def _format_tokens(tokens: int) -> str:
    """Format token count with k suffix for readability."""
    if tokens >= 1000:
        return f"{tokens / 1000:.1f}k"
    return f"{tokens}"


def _format_duration(duration_ms: float) -> str:
    """Format duration in human-readable form."""
    if duration_ms >= 1000:
        return f"{duration_ms / 1000:.1f}s"
    return f"{duration_ms:.0f}ms"


def _format_model(model: str) -> str:
    """Format model name, truncating provider prefix and long names."""
    # Strip common provider prefixes for cleaner display
    prefixes = ("anthropic/", "openai/", "google/", "mistral/")
    for prefix in prefixes:
        if model.startswith(prefix):
            model = model[len(prefix) :]
            break
    if len(model) > 20:
        return model[:17] + "..."
    return model


def _build_separator() -> Text:
    """Build horizontal separator line."""
    return Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")


def render_agent_response(
    content: str,
    tokens: int = 0,
    duration_ms: float = 0.0,
    model: str = "",
) -> RenderableType:
    """Render agent response in a styled 3-zone panel.

    Args:
        content: Markdown content from the agent
        tokens: Completion token count
        duration_ms: Request duration in milliseconds
        model: Model name used for the response

    Returns:
        Rich Panel containing the formatted response
    """
    border_color = UI_COLORS["accent"]
    muted_color = UI_COLORS["muted"]
    timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")

    # Viewport (markdown content)
    viewport = Markdown(content)

    # Status bar
    status_parts = []
    if tokens > 0:
        status_parts.append(_format_tokens(tokens))
    if duration_ms > 0:
        status_parts.append(_format_duration(duration_ms))
    if model:
        status_parts.append(_format_model(model))

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

    return Panel(
        Group(*content_parts),
        title=f"[{border_color}]agent[/]",
        subtitle=f"[{muted_color}]{timestamp}[/]",
        border_style=Style(color=border_color),
        padding=(0, 1),
        expand=True,
    )
