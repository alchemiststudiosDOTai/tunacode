"""Support helpers for the Textual REPL app.

This module exists to keep `tunacode.ui.app` focused on UI composition and lifecycle
while hosting small, testable helpers and callback builders.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from rich.console import Console
from rich.text import Text
from tinyagent.agent_types import TextContent

from tunacode.constants import MAX_CALLBACK_CONTENT
from tunacode.types import (
    StreamResultProtocol,
    ToolArgs,
    ToolCallback,
    ToolCallPartProtocol,
    ToolName,
    ToolResult,
    ToolResultCallback,
)

from tunacode.ui.widgets import ToolResultDisplay

if TYPE_CHECKING:
    from tunacode.core.session import StateManager

COLLAPSE_THRESHOLD: int = 10

FILE_EDIT_TOOLS: frozenset[str] = frozenset({"write_file", "hashline_edit"})

USER_MESSAGE_PREFIX: str = "│ "
DEFAULT_USER_MESSAGE_WIDTH: int = 80
CALLBACK_TRUNCATION_NOTICE: str = "\n... [truncated for safety]"
CALLBACK_TRUNCATION_NOTICE_LEN: int = len(CALLBACK_TRUNCATION_NOTICE)
AT_MENTION_PATTERN: re.Pattern[str] = re.compile(r"(?<!\S)@(?P<path>\S+)")
AT_MENTION_TRAILING_PUNCTUATION: str = ".,:;!?)]}"

def _format_prefixed_wrapped_lines(
    lines: list[tuple[str, str]],
    *,
    width: int,
) -> Text:
    effective_width = width if width > 0 else DEFAULT_USER_MESSAGE_WIDTH
    content_width = max(1, effective_width - len(USER_MESSAGE_PREFIX))
    console = Console(width=content_width, color_system=None, force_terminal=False)

    block = Text()
    for line_text, line_style in lines:
        wrapped_lines = Text(line_text, style=line_style, overflow="fold").wrap(
            console, content_width
        )
        for wrapped in wrapped_lines:
            block.append(USER_MESSAGE_PREFIX, style=line_style)
            block.append_text(wrapped)
            block.append("\n")
    return block


def format_user_message(text: str, style: str, *, width: int) -> Text:
    """Format user text with left gutter prefix and hard-wrap for terminal width."""
    lines = text.splitlines() or [""]
    styled_lines = [(line, style) for line in lines]
    return _format_prefixed_wrapped_lines(styled_lines, width=width)


def format_collapsed_message(text: str, style: str, *, width: int) -> Text:
    """Format long pasted text with a collapsed middle section.

    Shows first 3 lines, collapse indicator, and last 2 lines.
    """
    lines = text.splitlines()
    line_count = max(1, len(lines))

    if line_count <= COLLAPSE_THRESHOLD:
        return format_user_message(text, style, width=width)

    collapsed = line_count - 5

    render_lines: list[tuple[str, str]] = [(line, style) for line in lines[:3]]
    render_lines.append((f"[[ {collapsed} more lines ]]", f"dim {style}"))
    render_lines.extend((line, style) for line in lines[-2:])
    return _format_prefixed_wrapped_lines(render_lines, width=width)


def _split_mention_path(token: str) -> tuple[str, str]:
    path_token = token.rstrip(AT_MENTION_TRAILING_PUNCTUATION)
    trailing = token[len(path_token) :]
    return path_token, trailing


def _resolve_mentioned_path(path_token: str, cwd: Path) -> Path | None:
    if not path_token:
        return None

    candidate = Path(path_token).expanduser()
    if not candidate.is_absolute():
        candidate = cwd / candidate

    resolved = candidate.resolve()
    if not resolved.exists():
        return None
    return resolved


def normalize_agent_message_text(text: str, *, cwd: Path | None = None) -> str:
    """Replace @file mentions with absolute existing paths for agent execution."""
    if "@" not in text:
        return text

    base_dir = cwd or Path.cwd()

    def _replace(match: re.Match[str]) -> str:
        token = match.group("path")
        path_token, trailing = _split_mention_path(token)
        resolved = _resolve_mentioned_path(path_token, base_dir)
        if resolved is None:
            return match.group(0)
        resolved_path = resolved.as_posix()
        return f"{resolved_path}{trailing}"

    return AT_MENTION_PATTERN.sub(_replace, text)


class AppForCallbacks(Protocol):
    def post_message(self, message: ToolResultDisplay) -> bool: ...


def build_textual_tool_callback() -> ToolCallback:
    async def _callback(
        _part: ToolCallPartProtocol,
        _node: StreamResultProtocol,
    ) -> None:
        return None

    return _callback


def _truncate_for_safety(content: str | None) -> str | None:
    """Emergency truncation - prevents UI freeze on massive outputs."""
    if content is None:
        return None
    if len(content) <= MAX_CALLBACK_CONTENT:
        return content

    truncation_limit = MAX_CALLBACK_CONTENT - CALLBACK_TRUNCATION_NOTICE_LEN
    return content[:truncation_limit] + CALLBACK_TRUNCATION_NOTICE


def _extract_tool_result_text(result: ToolResult | None) -> str | None:
    if result is None:
        return None

    parts: list[str] = []
    for item in result.content:
        if not isinstance(item, TextContent):
            continue
        if isinstance(item.text, str):
            parts.append(item.text)

    return "".join(parts) if parts else None


def _is_validation_error(result: str | None) -> bool:
    """Check if result is a validation error that should go to model, not user."""
    if result is None:
        return False
    return "Invalid arguments for tool" in result and "missing a required argument" in result


def build_tool_result_callback(app: AppForCallbacks) -> ToolResultCallback:
    def _callback(
        tool_name: ToolName,
        status: str,
        args: ToolArgs,
        result: ToolResult | None = None,
        duration_ms: float | None = None,
    ) -> None:
        # Don't show validation errors to users - they go back to model for retry
        result_text = _extract_tool_result_text(result)

        if status == "failed" and _is_validation_error(result_text):
            return

        safe_result = _truncate_for_safety(result_text)

        app.post_message(
            ToolResultDisplay(
                tool_name=tool_name,
                status=status,
                args=args,
                result=result,
                result_text=safe_result,
                duration_ms=duration_ms,
            )
        )

    return _callback


async def run_textual_repl(state_manager: StateManager, show_setup: bool = False) -> None:
    from tunacode.ui.app import TextualReplApp

    app = TextualReplApp(state_manager=state_manager, show_setup=show_setup)
    await app.run_async()
