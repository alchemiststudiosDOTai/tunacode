"""Session state sub-structures for SessionState decomposition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tunacode.types.canonical import TodoItem
from tunacode.types.pydantic_ai import MessageHistory
from tunacode.types.tool_registry import ToolCallRegistry

REACT_TIMELINE_KEY = "timeline"

USAGE_KEY_PROMPT_TOKENS = "prompt_tokens"
USAGE_KEY_COMPLETION_TOKENS = "completion_tokens"
USAGE_KEY_COST = "cost"

DEFAULT_BATCH_COUNTER = 0
DEFAULT_CONSECUTIVE_EMPTY_RESPONSES = 0
DEFAULT_FORCED_CALLS = 0
DEFAULT_ITERATION_COUNT = 0
DEFAULT_MAX_TOKENS = 0
DEFAULT_REQUEST_ID = ""
DEFAULT_TOTAL_TOKENS = 0

DEFAULT_ORIGINAL_QUERY = ""
DEFAULT_USAGE_COMPLETION_TOKENS = 0
DEFAULT_USAGE_COST = 0.0
DEFAULT_USAGE_PROMPT_TOKENS = 0


def _default_react_scratchpad() -> dict[str, Any]:
    return {REACT_TIMELINE_KEY: []}


def _default_usage_metrics() -> dict[str, int | float]:
    return {
        USAGE_KEY_PROMPT_TOKENS: DEFAULT_USAGE_PROMPT_TOKENS,
        USAGE_KEY_COMPLETION_TOKENS: DEFAULT_USAGE_COMPLETION_TOKENS,
        USAGE_KEY_COST: DEFAULT_USAGE_COST,
    }


@dataclass(slots=True)
class ConversationState:
    """Conversation history and token tracking."""

    messages: MessageHistory = field(default_factory=list)
    thoughts: list[str] = field(default_factory=list)
    total_tokens: int = DEFAULT_TOTAL_TOKENS
    max_tokens: int = DEFAULT_MAX_TOKENS
    files_in_context: set[str] = field(default_factory=set)


@dataclass(slots=True)
class ReActState:
    """ReAct scratchpad and guidance tracking."""

    scratchpad: dict[str, Any] = field(default_factory=_default_react_scratchpad)
    forced_calls: int = DEFAULT_FORCED_CALLS
    guidance: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TaskState:
    """Todo state and original task context."""

    todos: list[TodoItem] = field(default_factory=list)
    original_query: str = DEFAULT_ORIGINAL_QUERY


@dataclass(slots=True)
class RuntimeState:
    """Per-run counters, tool tracking, and streaming flags."""

    current_iteration: int = DEFAULT_ITERATION_COUNT
    iteration_count: int = DEFAULT_ITERATION_COUNT
    request_id: str = DEFAULT_REQUEST_ID
    consecutive_empty_responses: int = DEFAULT_CONSECUTIVE_EMPTY_RESPONSES
    batch_counter: int = DEFAULT_BATCH_COUNTER
    tool_registry: ToolCallRegistry = field(default_factory=ToolCallRegistry)
    operation_cancelled: bool = False
    is_streaming_active: bool = False
    streaming_panel: Any | None = None


@dataclass(slots=True)
class UsageState:
    """Usage metrics for last call and cumulative session totals."""

    last_call_usage: dict[str, int | float] = field(default_factory=_default_usage_metrics)
    session_total_usage: dict[str, int | float] = field(default_factory=_default_usage_metrics)


__all__ = [
    "ConversationState",
    "ReActState",
    "RuntimeState",
    "TaskState",
    "UsageState",
]
