"""Textual message classes for widget communication."""

from __future__ import annotations

from collections.abc import Iterable

from rich.console import RenderableType
from textual.message import Message

from tunacode.types import ToolArgs, ToolName, ToolResult


class EditorCompletionsAvailable(Message):
    """Notify the app when multiple completions are available."""

    def __init__(self, *, candidates: Iterable[str]) -> None:
        super().__init__()
        self.candidates = list(candidates)


class EditorSubmitRequested(Message):
    """Submit event for the current editor content."""

    def __init__(self, *, text: str, raw_text: str, was_pasted: bool = False) -> None:
        super().__init__()
        self.text = text
        self.raw_text = raw_text
        self.was_pasted = was_pasted


class ToolResultDisplay(Message):
    """Request to display a tool result panel in the RichLog."""

    def __init__(
        self,
        *,
        tool_name: ToolName,
        status: str,
        args: ToolArgs,
        result: ToolResult | None = None,
        result_text: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.status = status
        self.args = args
        self.result = result
        self.result_text = result_text
        self.duration_ms = duration_ms


class TuiLogDisplay(Message):
    """Request to display a renderable in the chat container on the UI thread."""

    def __init__(self, *, renderable: RenderableType) -> None:
        super().__init__()
        self.renderable = renderable


class SystemNoticeDisplay(Message):
    """Request to display a system notice on the UI thread."""

    def __init__(self, *, notice: str) -> None:
        super().__init__()
        self.notice = notice


class CompactionStatusChanged(Message):
    """Request to update compaction status on the UI thread."""

    def __init__(self, *, active: bool) -> None:
        super().__init__()
        self.active = active
