"""Session state sub-structures for SessionState decomposition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tunacode.types.canonical import UsageMetrics

from tunacode.infrastructure.llm_types import MessageHistory

from tunacode.core.types.tool_registry import ToolCallRegistry

DEFAULT_BATCH_COUNTER = 0
DEFAULT_CONSECUTIVE_EMPTY_RESPONSES = 0
DEFAULT_ITERATION_COUNT = 0
DEFAULT_MAX_TOKENS = 0
DEFAULT_REQUEST_ID = ""
DEFAULT_TOTAL_TOKENS = 0

DEFAULT_ORIGINAL_QUERY = ""


@dataclass(slots=True)
class ConversationState:
    """Conversation history and token tracking."""

    messages: MessageHistory = field(default_factory=list)
    thoughts: list[str] = field(default_factory=list)
    total_tokens: int = DEFAULT_TOTAL_TOKENS
    max_tokens: int = DEFAULT_MAX_TOKENS
    files_in_context: set[str] = field(default_factory=set)


@dataclass(slots=True)
class TaskState:
    """Original task context."""

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

    last_call_usage: UsageMetrics = field(default_factory=UsageMetrics)
    session_total_usage: UsageMetrics = field(default_factory=UsageMetrics)


__all__ = [
    "ConversationState",
    "RuntimeState",
    "TaskState",
    "UsageState",
]
