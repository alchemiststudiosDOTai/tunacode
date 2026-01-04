"""Message renderers for user messages, AI responses, and thinking blocks.

Provides distinct visual styling for different message types following
NeXTSTEP-inspired design principles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from rich.console import RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from tunacode.constants import (
    MESSAGE_BLOCK_WIDTH,
    THINKING_COLLAPSED_LINES,
    THINKING_PREFIX,
    UI_COLORS,
)


@dataclass
class UserMessageData:
    """Data for rendering a user message."""

    content: str
    timestamp: datetime
    width: int = MESSAGE_BLOCK_WIDTH


@dataclass
class AIResponseData:
    """Data for rendering an AI response."""

    content: str
    model: str
    duration_ms: float | None = None
    token_count: int | None = None


@dataclass
class ThinkingBlockData:
    """Data for rendering a thinking/reasoning block."""

    content: str
    collapsed: bool = True


class MessageRenderer:
    """Static methods for rendering different message types."""

    @staticmethod
    def render_user_message(data: UserMessageData) -> RenderableType:
        """Render a user message with left border and timestamp footer.

        Example output:
            ┃ What files are in src?
            ┃ you 3:42 PM
        """
        primary = UI_COLORS["primary"]

        lines = data.content.split("\n")
        result = Text()

        for line in lines:
            result.append("┃ ", style=primary)
            result.append(f"{line}\n")

        # Add timestamp footer
        timestamp_str = data.timestamp.strftime("%I:%M %p").lstrip("0")
        result.append("┃ ", style=primary)
        result.append(f"you {timestamp_str}", style=f"dim {primary}")

        return result

    @staticmethod
    def render_ai_response(data: AIResponseData) -> RenderableType:
        """Render an AI response in a bordered panel with metadata footer.

        Example output:
            ╭─ agent ─────────────────────────────────────────╮
            │ Here are the files:                             │
            │ - main.py                                       │
            │ - utils.py                                      │
            ├─────────────────────────────────────────────────┤
            │ gpt-4o • 1.2s • 127 tokens                      │
            ╰─────────────────────────────────────────────────╯
        """
        accent = UI_COLORS["accent"]
        muted = UI_COLORS["muted"]

        # Build metadata footer parts
        footer_parts: list[str] = []

        # Model name (extract short name from full model string)
        model_short = data.model.split("/")[-1] if "/" in data.model else data.model
        footer_parts.append(model_short)

        # Duration
        if data.duration_ms is not None:
            if data.duration_ms >= 1000:
                footer_parts.append(f"{data.duration_ms / 1000:.1f}s")
            else:
                footer_parts.append(f"{data.duration_ms:.0f}ms")

        # Token count
        if data.token_count is not None:
            footer_parts.append(f"{data.token_count} tokens")

        footer_text = " • ".join(footer_parts)

        # Use a Group to combine Markdown with footer
        from rich.console import Group

        markdown_content = Markdown(data.content)

        footer = Text()
        footer.append("\n")
        footer.append(footer_text, style=muted)

        return Panel(
            Group(markdown_content, footer),
            title=f"[{accent}]agent[/]",
            title_align="left",
            border_style=Style(color=accent),
            padding=(0, 1),
            expand=True,
            width=MESSAGE_BLOCK_WIDTH,
        )

    @staticmethod
    def render_thinking(data: ThinkingBlockData) -> RenderableType:
        """Render a thinking/reasoning block with gray left border, dimmed.

        Example output:
            ┃ Thinking: I need to list the directory...
        """
        muted = UI_COLORS["muted"]

        content = data.content.strip()

        if data.collapsed:
            # Show only first few lines when collapsed
            lines = content.split("\n")
            if len(lines) > THINKING_COLLAPSED_LINES:
                content = "\n".join(lines[:THINKING_COLLAPSED_LINES]) + "\n..."

        result = Text()
        result.append("┃ ", style=muted)
        result.append(f"{THINKING_PREFIX} ", style=f"bold {muted}")
        result.append(content, style=muted)

        return result


def extract_thinking(content: str) -> tuple[str, str | None]:
    """Extract <thinking>...</thinking> content from response.

    Returns:
        Tuple of (content_without_thinking, thinking_content_or_none)
    """
    pattern = r"<thinking>(.*?)</thinking>"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        thinking_content = match.group(1).strip()
        content_without = re.sub(pattern, "", content, flags=re.DOTALL).strip()
        return content_without, thinking_content

    return content, None
