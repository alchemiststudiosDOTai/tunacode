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
from typing import Any, Protocol, TypeAlias, runtime_checkable

from tunacode.types.base import ToolArgs, ToolName

# =============================================================================
# Protocol Types (Framework-Agnostic)
# =============================================================================
# These protocols define the shape expected by callbacks without coupling
# to any specific LLM framework. Infrastructure adapters implement these.


@runtime_checkable
class ToolCallPartProtocol(Protocol):
    """Protocol for tool call objects passed to callbacks.

    Any object with these attributes satisfies the protocol:
    - tool_call_id: Unique identifier for the tool call
    - tool_name: Name of the tool being invoked
    - args: Arguments passed to the tool
    """

    tool_call_id: str
    tool_name: str
    args: dict[str, Any]


@runtime_checkable
class StreamResultProtocol(Protocol):
    """Protocol for streaming result context objects.

    This is passed to tool callbacks for result submission.
    The actual implementation details are framework-specific.
    """

    # Marker protocol - concrete attributes are framework-specific
    pass


# =============================================================================
# Tool Callbacks
# =============================================================================

# Tool callback using protocol types (framework-agnostic)
ToolCallback: TypeAlias = Callable[
    [ToolCallPartProtocol, StreamResultProtocol],
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
    # Protocol types
    "ToolCallPartProtocol",
    "StreamResultProtocol",
    # Tool callbacks
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
