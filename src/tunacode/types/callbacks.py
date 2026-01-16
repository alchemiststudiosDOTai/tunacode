"""Callback type definitions for TunaCode CLI.

Contains callback signatures and the ToolProgress dataclass for
structured progress reporting.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolProgress:
    """Structured progress information for subagent tool execution.

    Attributes:
        subagent: Name of the subagent (e.g., "research")
        operation: Description of current operation (e.g., "grep pattern...")
        current: Current operation count (1-indexed)
        total: Total expected operations (0 if unknown)
    """

    subagent: str
    operation: str
    current: int
    total: int


# Tool callbacks
ToolCallback = Callable[[Any, Any], Awaitable[None]]
ToolStartCallback = Callable[[str], None]
ToolProgressCallback = Callable[[ToolProgress], None]
NoticeCallback = Callable[[str], None]

# UI callbacks
UICallback = Callable[[str], Awaitable[None]]
UIInputCallback = Callable[[str, str], Awaitable[str]]

# Async function types
AsyncFunc = Callable[..., Awaitable[Any]]
AsyncToolFunc = Callable[..., Awaitable[str]]
AsyncVoidFunc = Callable[..., Awaitable[None]]

__all__ = [
    "AsyncFunc",
    "AsyncToolFunc",
    "AsyncVoidFunc",
    "ToolCallback",
    "ToolProgress",
    "ToolProgressCallback",
    "ToolStartCallback",
    "NoticeCallback",
    "UICallback",
    "UIInputCallback",
]
