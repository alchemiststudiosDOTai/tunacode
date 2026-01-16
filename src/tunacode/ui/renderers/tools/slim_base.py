"""Slim panel utilities for NeXTSTEP-style tool renderers.

Provides utilities for building thin framed boxes matching the dream mockup:
- Thin rounded box with title in top border
- Cyan underlined subtitles (↳ filepath)
- Full-line background colors for semantic highlighting
"""

from __future__ import annotations

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from tunacode.constants import (
    SLIM_BG_ADDED,
    SLIM_BG_CONTENT,
    SLIM_BG_ERROR,
    SLIM_BG_REMOVED,
    SLIM_BG_WARNING,
    SLIM_BORDER_COLOR,
    SLIM_PANEL_WIDTH,
    SLIM_SUBTITLE_STYLE,
)

# Thin box style matching dream mockup
SLIM_BOX = box.ROUNDED

# Pre-built styles for full-line backgrounds
STYLE_REMOVED = Style(bgcolor=SLIM_BG_REMOVED)
STYLE_ADDED = Style(bgcolor=SLIM_BG_ADDED)
STYLE_ERROR = Style(bgcolor=SLIM_BG_ERROR)
STYLE_WARNING = Style(bgcolor=SLIM_BG_WARNING)


def slim_subtitle(context: str, prefix: str = "↳ ") -> Text:
    """Build slim subtitle: ↳ context (cyan, underlined)

    Args:
        context: Context text (filepath, command, pattern, etc.)
        prefix: Prefix character (default: ↳)

    Returns:
        Rich Text object with cyan underlined styling
    """
    subtitle = Text()
    subtitle.append(prefix, style="dim")
    subtitle.append(context, style=SLIM_SUBTITLE_STYLE)
    return subtitle


def slim_footer(shown: int, total: int) -> Text:
    """Build slim footer with truncation info: [{shown}/{total}]

    Args:
        shown: Number of lines shown
        total: Total number of lines

    Returns:
        Rich Text object, empty if not truncated
    """
    if shown >= total:
        return Text("")

    return Text(f"[{shown}/{total}]", style="dim")


def slim_panel(
    name: str,
    content: RenderableType,
    stats: str = "",
    subtitle: str | None = None,
    footer: Text | None = None,
) -> Panel:
    """Create a thin framed panel matching dream mockup style.

    Creates a rounded box with:
    - Title (tool name) in top-left border
    - Stats in top-right border
    - Optional subtitle inside (↳ filepath)
    - Content with syntax highlighting background
    - Optional footer for truncation info

    Args:
        name: Tool name for title
        content: Main content renderable
        stats: Right-side stats (e.g., "42 files", "+3 -2")
        subtitle: Optional context (filepath, pattern, etc.)
        footer: Optional truncation info

    Returns:
        Rich Panel with thin frame
    """
    # Build inner content
    parts: list[RenderableType] = []

    if subtitle:
        parts.append(slim_subtitle(subtitle))
        parts.append(Text(""))  # Blank line after subtitle

    parts.append(content)

    if footer and str(footer):
        parts.append(footer)

    inner = Group(*parts) if len(parts) > 1 else parts[0]

    # Build title with stats on right
    title = f"[bold]{name}[/bold]"
    subtitle_text = stats if stats else None

    return Panel(
        inner,
        title=title,
        title_align="left",
        subtitle=subtitle_text,
        subtitle_align="right",
        box=SLIM_BOX,
        border_style=SLIM_BORDER_COLOR,
        style=f"on {SLIM_BG_CONTENT}",  # Dark background for content
        padding=(0, 1),
        expand=True,
    )


def styled_line(content: str, style: Style, width: int = SLIM_PANEL_WIDTH) -> Text:
    """Apply background color to entire line width.

    Creates a full-line background effect by padding the content to the specified width.

    Args:
        content: Line content
        style: Rich Style with bgcolor set
        width: Target width for full-line effect

    Returns:
        Rich Text object with full-line background
    """
    # Pad content to width for full-line background
    padded = content.ljust(width)
    text = Text(padded)
    text.stylize(style, 0, len(padded))
    return text


def diff_line(content: str, line_type: str, width: int = SLIM_PANEL_WIDTH) -> Text:
    """Create a diff line with appropriate background color.

    Args:
        content: Line content (including +/- prefix)
        line_type: One of "added", "removed", "context"
        width: Target width for full-line effect

    Returns:
        Rich Text object with appropriate styling
    """
    if line_type == "added":
        return styled_line(content, STYLE_ADDED, width)
    if line_type == "removed":
        return styled_line(content, STYLE_REMOVED, width)
    # Context line - no background
    return Text(content)


def diagnostic_line(
    content: str, severity: str, width: int = SLIM_PANEL_WIDTH
) -> Text:
    """Create a diagnostic line with appropriate background color.

    Args:
        content: Diagnostic message
        severity: One of "error", "warning", "info"
        width: Target width for full-line effect

    Returns:
        Rich Text object with appropriate styling
    """
    if severity == "error":
        return styled_line(content, STYLE_ERROR, width)
    if severity == "warning":
        return styled_line(content, STYLE_WARNING, width)
    # Info or unknown - no background
    return Text(content)
