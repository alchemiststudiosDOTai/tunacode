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


def _format_model(model: str) -> str:
    """Format model name, abbreviating provider prefix but keeping full model name.

    Precondition: model is a non-empty string
    Postcondition: Returns formatted model name, truncated if >30 chars
    """
    provider_abbrevs = {
        "anthropic/": "ANTH/",
        "openai/": "OA/",
        "google/": "GOOG/",
        "mistral/": "MIST/",
        "openrouter/": "OR/",
        "together/": "TOG/",
        "groq/": "GROQ/",
    }
    for prefix, abbrev in provider_abbrevs.items():
        if model.startswith(prefix):
            model = abbrev + model[len(prefix) :]
            break
    # Truncate absurdly long model names to prevent status bar overflow
    if len(model) > 30:
        return model[:27] + "..."
    return model


def _build_separator() -> Text:
    """Build horizontal separator line."""
    return Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")


def render_agent_streaming(
    content: str,
    elapsed_ms: float = 0.0,
    model: str = "",
) -> RenderableType:
    """Render streaming agent response in a NeXTSTEP panel.

    Uses same 3-zone layout as finalized response but with
    visual indicators for active streaming state.

    Preconditions:
        - elapsed_ms >= 0 (when provided)
        - content is a valid string (may be empty)

    Postconditions:
        - Returns a Rich Panel with streaming indicators
        - Panel expands to full width
        - Status bar shows streaming state with elapsed time and model

    Args:
        content: Current markdown content being streamed
        elapsed_ms: Time since streaming started
        model: Model name being used

    Returns:
        Rich Panel with streaming indicator
    """
    if elapsed_ms < 0:
        raise ValueError(f"elapsed_ms must be non-negative, got {elapsed_ms}")

    border_color = UI_COLORS["primary"]  # Primary color for "running" state
    muted_color = UI_COLORS["muted"]

    # Viewport (markdown content)
    viewport = Markdown(content) if content else Text("...", style="dim italic")

    # Status bar - streaming indicator
    status_parts = []
    if model:
        status_parts.append(_format_model(model))
    status_parts.append("streaming")
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

    return Panel(
        Group(*content_parts),
        title=f"[{border_color}]agent[/] [...]",
        border_style=Style(color=border_color),
        padding=(0, 1),
        expand=True,
    )


def render_agent_response(
    content: str,
    tokens: int = 0,
    duration_ms: float = 0.0,
    model: str = "",
) -> RenderableType:
    """Render agent response in a styled 3-zone panel.

    Preconditions:
        - tokens >= 0 (when provided)
        - duration_ms >= 0 (when provided)
        - content is a valid string

    Postconditions:
        - Returns a Rich Panel with formatted agent response
        - Panel expands to full width
        - Status bar shows metrics (tokens, duration, model) when available

    Args:
        content: Markdown content from the agent
        tokens: Completion token count
        duration_ms: Request duration in milliseconds
        model: Model name used for the response

    Returns:
        Rich Panel containing the formatted response
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
    status_parts = []
    if model:
        status_parts.append(_format_model(model))
    if tokens > 0:
        status_parts.append(_format_tokens(tokens))
    if duration_ms > 0:
        status_parts.append(_format_duration(duration_ms))

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
