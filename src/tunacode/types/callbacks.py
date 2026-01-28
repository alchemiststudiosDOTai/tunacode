"""Callback type definitions for TunaCode CLI.

Contains callback signatures and the ToolProgress dataclass for
structured progress reporting.

Callback contracts (preconditions/postconditions):
- ToolResultCallback: Preconditions: tool_name is registered, args are normalized,
  status reflects tool lifecycle. Postconditions: side effects only (UI/logging) and
  should not raise.
- StreamingCallback: Preconditions: chunk is ordered text delta. Postconditions:
  enqueue or render the chunk without raising.
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeAlias

from tunacode.types import ToolArgs, ToolName

if TYPE_CHECKING:
    from pydantic_ai.messages import ToolCallPart  # noqa: F401
    from pydantic_ai.result import StreamedRunResult  # noqa: F401


# Tool callbacks
ToolCallback: TypeAlias = Callable[
    ["ToolCallPart", "StreamedRunResult[None, str]"],
    Awaitable[None],
]
ToolStartCallback: TypeAlias = Callable[[str], None]
ToolResultCallback: TypeAlias = Callable[
    [ToolName, str, ToolArgs, str | None, float | None],
    None,
]
NoticeCallback: TypeAlias = Callable[[str], None]

# UI callbacks
StreamingCallback: TypeAlias = Callable[[str], Awaitable[None]]
UICallback: TypeAlias = Callable[[str], Awaitable[None]]
UIInputCallback: TypeAlias = Callable[[str, str], Awaitable[str]]

# Async function types
AsyncFunc: TypeAlias = Callable[..., Awaitable[Any]]
AsyncToolFunc: TypeAlias = Callable[..., Awaitable[str]]
AsyncVoidFunc: TypeAlias = Callable[..., Awaitable[None]]

__all__ = [
    "AsyncFunc",
    "AsyncToolFunc",
    "AsyncVoidFunc",
    "StreamingCallback",
    "ToolCallback",
    "ToolResultCallback",
    "ToolStartCallback",
    "NoticeCallback",
    "UICallback",
    "UIInputCallback",
]
