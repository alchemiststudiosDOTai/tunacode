"""Support helpers for the Textual REPL app.

This module exists to keep `tunacode.ui.app` focused on UI composition and lifecycle
while hosting small, testable helpers and callback builders.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from rich.console import Console
from rich.text import Text

from tunacode.constants import MAX_CALLBACK_CONTENT
from tunacode.tools.authorization.handler import ToolHandler
from tunacode.types import (
    StateManager,
    ToolConfirmationRequest,
    ToolConfirmationResponse,
)
from tunacode.ui.widgets import ToolResultDisplay

COLLAPSE_THRESHOLD: int = 10

FILE_EDIT_TOOLS: frozenset[str] = frozenset({"write_file", "update_file"})

USER_MESSAGE_PREFIX: str = "│ "
DEFAULT_USER_MESSAGE_WIDTH: int = 80


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


@dataclass
class PendingConfirmationState:
    """Tracks pending tool confirmation state."""

    future: asyncio.Future[ToolConfirmationResponse]
    request: ToolConfirmationRequest


class ConfirmationRequester(Protocol):
    async def request_tool_confirmation(
        self, request: ToolConfirmationRequest
    ) -> ToolConfirmationResponse: ...


class StatusBarLike(Protocol):
    def add_edited_file(self, filepath: str) -> None: ...

    def update_last_action(self, tool_name: str) -> None: ...

    def update_running_action(self, tool_name: str) -> None: ...

    def update_subagent_progress(
        self, subagent: str, operation: str, current: int, total: int
    ) -> None: ...


class AppForCallbacks(ConfirmationRequester, Protocol):
    status_bar: StatusBarLike

    def post_message(self, message: ToolResultDisplay) -> None: ...


def build_textual_tool_callback(
    app: ConfirmationRequester,
    state_manager: StateManager,
) -> Callable[[Any, Any | None], Awaitable[None]]:
    async def _callback(part: Any, _node: Any = None) -> None:
        tool_handler = state_manager.tool_handler or ToolHandler(state_manager)
        state_manager.set_tool_handler(tool_handler)

        if not tool_handler.should_confirm(part.tool_name):
            return

        from tunacode.exceptions import UserAbortError
        from tunacode.utils.parsing.command_parser import parse_args

        args = parse_args(part.args)
        request = tool_handler.create_confirmation_request(part.tool_name, args)
        response = await app.request_tool_confirmation(request)
        if not tool_handler.process_confirmation(response, part.tool_name):
            raise UserAbortError("User aborted tool execution")

    return _callback


def _truncate_for_safety(content: str | None) -> str | None:
    """Emergency truncation - prevents UI freeze on massive outputs."""
    if content is None:
        return None
    if len(content) <= MAX_CALLBACK_CONTENT:
        return content
    return content[:MAX_CALLBACK_CONTENT] + "\n... [truncated for safety]"


def build_tool_result_callback(app: AppForCallbacks) -> Callable[..., None]:
    def _callback(
        tool_name: str,
        status: str,
        args: dict[str, Any],
        result: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        if tool_name in FILE_EDIT_TOOLS and status == "completed":
            filepath = args.get("filepath")
            if filepath:
                app.status_bar.add_edited_file(filepath)

        app.status_bar.update_last_action(tool_name)

        safe_result = _truncate_for_safety(result)

        app.post_message(
            ToolResultDisplay(
                tool_name=tool_name,
                status=status,
                args=args,
                result=safe_result,
                duration_ms=duration_ms,
            )
        )

    return _callback


def build_tool_start_callback(app: AppForCallbacks) -> Callable[[str], None]:
    """Build callback for tool start notifications."""

    def _callback(tool_name: str) -> None:
        app.status_bar.update_running_action(tool_name)

    return _callback


def build_tool_progress_callback(app: AppForCallbacks) -> Callable[[str, str, int, int], None]:
    """Build callback for subagent tool progress notifications."""

    def _callback(subagent: str, operation: str, current: int, total: int) -> None:
        app.status_bar.update_subagent_progress(subagent, operation, current, total)

    return _callback


async def run_textual_repl(state_manager: StateManager, show_setup: bool = False) -> None:
    from tunacode.ui.app import TextualReplApp

    app = TextualReplApp(state_manager=state_manager, show_setup=show_setup)
    await app.run_async()
