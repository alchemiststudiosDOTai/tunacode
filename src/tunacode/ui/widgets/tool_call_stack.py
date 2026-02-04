"""Tool call stack widget.

Displays a compact list of tool calls (invocations) rather than full tool output panels.
This is intended to match the dream UI where tool bursts are summarized as:

    ▶ glob       [ *.json ]
    ▶ read_file  index.html

The widget is designed to be mounted into ChatContainer and updated in-place.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text
from textual.widgets import Static

from tunacode.ui.styles import STYLE_ACCENT, STYLE_MUTED, STYLE_PRIMARY
from tunacode.ui.widgets.messages import ToolResultDisplay

TOOL_CALL_PREFIX: str = "▶ "
TOOL_NAME_COLUMN_WIDTH: int = 12

DEFAULT_MAX_VISIBLE_CALLS: int = 3
MAX_ARG_DISPLAY_CHARS: int = 40
ELLIPSIS: str = "…"


class ToolCallStack(Static):
    """A compact, updateable display of recent tool calls."""

    def __init__(
        self,
        *,
        max_visible_calls: int = DEFAULT_MAX_VISIBLE_CALLS,
    ) -> None:
        super().__init__("")
        self._max_visible_calls = max(1, max_visible_calls)
        self._calls: list[ToolResultDisplay] = []

    def set_calls(self, calls: list[ToolResultDisplay]) -> None:
        self._calls = list(calls)
        self.update(self._render())

    def append_calls(self, calls: list[ToolResultDisplay]) -> None:
        self._calls.extend(calls)
        self.update(self._render())

    def append_call(self, call: ToolResultDisplay) -> None:
        self._calls.append(call)
        self.update(self._render())

    def _render(self) -> RenderableType:
        visible_count = self._max_visible_calls
        total = len(self._calls)

        call_slice = self._calls[-visible_count:]
        hidden_count = max(0, total - len(call_slice))

        lines: list[Text] = []
        if hidden_count:
            lines.append(Text(f"{ELLIPSIS} +{hidden_count} more", style=STYLE_MUTED))

        for call in call_slice:
            lines.append(_format_tool_call_row(call))

        return Group(*lines)


def _format_tool_call_row(call: ToolResultDisplay) -> Text:
    tool_name = str(call.tool_name)
    args = call.args

    row = Text()
    row.append(TOOL_CALL_PREFIX, style=STYLE_PRIMARY)
    row.append(f"{tool_name:<{TOOL_NAME_COLUMN_WIDTH}}", style=f"bold {STYLE_PRIMARY}")

    key_arg = _extract_key_arg(tool_name, args)
    if key_arg:
        row.append(" ")
        row.append(key_arg, style=f"underline {STYLE_ACCENT}")

    return row


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
        return _truncate(f"[ {value} ]", MAX_ARG_DISPLAY_CHARS)

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

    # Deterministic fallback: first key by sorted order.
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


def tool_call_signature(call: ToolResultDisplay) -> str:
    """Return a stable signature for suppressing tool result panels.

    This is a best-effort signature (until tool_call_id is threaded through to the UI).
    """
    args_json = json.dumps(call.args or {}, sort_keys=True, default=str)
    return f"{call.tool_name}:{args_json}"
