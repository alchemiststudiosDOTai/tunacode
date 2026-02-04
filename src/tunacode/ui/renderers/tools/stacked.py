"""Stacked (compressed) tool result renderer.

This renderer is used when many tool results arrive in a short burst.
Rather than rendering full 4-zone tool panels for each tool, we render a
single panel containing one compact row per tool.

Design intent:
- Preserve NeXTSTEP-style uniformity (single bordered panel, consistent width)
- Keep the user informed while reducing vertical space
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from tunacode.core.constants import UI_COLORS

from tunacode.ui.renderers.panel_widths import tool_panel_frame_width
from tunacode.ui.styles import STYLE_ERROR, STYLE_MUTED, STYLE_PRIMARY, STYLE_WARNING
from tunacode.ui.widgets import ToolResultDisplay

TOOL_NAME_COLUMN_WIDTH: int = 12
MAX_ARG_DISPLAY_CHARS: int = 40
ELLIPSIS: str = "…"


def render_stacked_tools(
    tools: list[ToolResultDisplay],
    *,
    max_line_width: int,
) -> RenderableType:
    """Render a batch of tools as compact single-line rows.

    Args:
        tools: The tool display messages to render.
        max_line_width: Maximum line width used to match other tool panel widths.

    Returns:
        A Rich Panel containing one row per tool.
    """
    if not tools:
        raise ValueError("render_stacked_tools requires at least one tool")

    rows: list[Text] = []
    for tool in tools:
        tool_name = str(tool.tool_name)
        args = tool.args
        key_arg = _extract_key_arg(tool_name, args)
        is_failed = tool.status != "completed"

        row = Text()
        row.append("> ", style=STYLE_MUTED)

        name_style = f"bold {STYLE_PRIMARY}" if not is_failed else f"bold {STYLE_ERROR}"
        row.append(f"{tool_name:<{TOOL_NAME_COLUMN_WIDTH}}", style=name_style)

        if key_arg:
            arg_style = STYLE_WARNING if not is_failed else STYLE_ERROR
            row.append(" ")
            row.append(key_arg, style=arg_style)

        if is_failed:
            row.append(" ")
            row.append("[FAILED]", style=f"bold {STYLE_ERROR}")

        rows.append(row)

    content = Group(*rows)
    frame_width = tool_panel_frame_width(max_line_width)

    timestamp = datetime.now().strftime("%H:%M:%S")

    return Panel(
        content,
        title=f"[{STYLE_PRIMARY}]tools[/] [dim]batch ({len(tools)})[/]",
        subtitle=f"[{STYLE_MUTED}]{timestamp}[/]",
        border_style=Style(color=UI_COLORS["muted"]),
        padding=(0, 1),
        width=frame_width,
    )


def _extract_key_arg(tool_name: str, args: dict[str, Any] | None) -> str:
    if not args:
        return ""

    normalized_name = tool_name.lower()

    key = _tool_primary_arg_key(normalized_name)
    if key is None:
        return _truncate(_format_fallback_arg(args), MAX_ARG_DISPLAY_CHARS)

    value = args.get(key)
    if value is None:
        return ""

    if normalized_name == "glob":
        rendered = f"[ {value} ]"
        return _truncate(rendered, MAX_ARG_DISPLAY_CHARS)

    if normalized_name == "grep" and key == "pattern":
        rendered = f"{value!s}"
        return _truncate(rendered, MAX_ARG_DISPLAY_CHARS)

    return _truncate(str(value), MAX_ARG_DISPLAY_CHARS)


def _tool_primary_arg_key(tool_name: str) -> str | None:
    mapping: dict[str, str] = {
        "glob": "pattern",
        "read_file": "filepath",
        "list_dir": "directory",
        "grep": "pattern",
        "bash": "command",
        "write_file": "filepath",
        "update_file": "filepath",
        "web_fetch": "url",
    }
    return mapping.get(tool_name)


def _format_fallback_arg(args: dict[str, Any]) -> str:
    for key in ("filepath", "path", "pattern", "query", "command", "url", "directory"):
        value = args.get(key)
        if value is None:
            continue
        return f"{key}={value}"

    # Deterministic fallback: first key by sorted order
    first_key = next(iter(sorted(args.keys())), "")
    if not first_key:
        return ""

    return f"{first_key}={args.get(first_key)}"


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    if max_chars <= len(ELLIPSIS):
        return ELLIPSIS[:max_chars]

    head_len = max_chars - len(ELLIPSIS)
    return f"{text[:head_len]}{ELLIPSIS}"
