"""Renderer for muted streaming thinking content."""

from __future__ import annotations

from rich.text import Text

from tunacode.ui.styles import STYLE_MUTED
from tunacode.ui.widgets.chat import PanelMeta

DEFAULT_THINKING_MAX_LINES: int = 10
DEFAULT_THINKING_MAX_CHARS: int = 1200
THINKING_PANEL_CSS_CLASS: str = "thinking-panel"
THINKING_PANEL_TITLE: str = "thought"
THINKING_TRUNCATION_MARKER_TEMPLATE: str = "[[ {hidden_line_count} earlier lines hidden ]]"
THINKING_CHAR_TRUNCATION_MARKER: str = "[[ earlier content hidden ]]"


def render_thinking(
    content: str,
    max_lines: int = DEFAULT_THINKING_MAX_LINES,
    *,
    max_chars: int = DEFAULT_THINKING_MAX_CHARS,
) -> Text:
    """Render reasoning text in a muted, line-bounded format."""
    if max_lines < 1:
        raise ValueError(f"max_lines must be >= 1, got {max_lines}")
    if max_chars < 1:
        raise ValueError(f"max_chars must be >= 1, got {max_chars}")

    chars_hidden = len(content) > max_chars
    visible_content = content[-max_chars:] if chars_hidden else content

    lines = visible_content.splitlines()
    if not lines:
        return Text("", style=STYLE_MUTED)

    hidden_line_count = len(lines) - max_lines
    visible_lines = lines[-max_lines:] if hidden_line_count > 0 else lines

    markers: list[str] = []
    if chars_hidden:
        markers.append(THINKING_CHAR_TRUNCATION_MARKER)
    if hidden_line_count > 0:
        markers.append(
            THINKING_TRUNCATION_MARKER_TEMPLATE.format(hidden_line_count=hidden_line_count)
        )

    rendered_parts: list[str] = []
    if markers:
        rendered_parts.append("\n".join(markers))
    rendered_parts.append("\n".join(visible_lines))
    rendered_content = "\n".join(rendered_parts)
    return Text(rendered_content, style=STYLE_MUTED)


def render_thinking_panel(
    content: str,
    max_lines: int = DEFAULT_THINKING_MAX_LINES,
    *,
    max_chars: int = DEFAULT_THINKING_MAX_CHARS,
) -> tuple[Text, PanelMeta]:
    """Render thinking content with panel metadata for ChatContainer flow."""
    thinking_text = render_thinking(content, max_lines=max_lines, max_chars=max_chars)
    panel_meta = PanelMeta(
        css_class=THINKING_PANEL_CSS_CLASS,
        border_title=f"[{STYLE_MUTED}]{THINKING_PANEL_TITLE}[/]",
    )
    return thinking_text, panel_meta
