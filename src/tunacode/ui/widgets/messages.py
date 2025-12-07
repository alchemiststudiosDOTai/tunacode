"""Textual message classes for widget communication."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from textual.message import Message


class EditorCompletionsAvailable(Message):
    """Notify the app when multiple completions are available."""

    def __init__(self, *, candidates: Iterable[str]) -> None:
        super().__init__()
        self.candidates = list(candidates)


class EditorSubmitRequested(Message):
    """Submit event for the current editor content."""

    def __init__(self, *, text: str, raw_text: str) -> None:
        super().__init__()
        self.text = text
        self.raw_text = raw_text


class ToolResultDisplay(Message):
    """Request to display a tool result panel in the RichLog."""

    def __init__(
        self,
        *,
        tool_name: str,
        status: str,
        args: dict[str, Any],
        result: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.status = status
        self.args = args
        self.result = result
        self.duration_ms = duration_ms
