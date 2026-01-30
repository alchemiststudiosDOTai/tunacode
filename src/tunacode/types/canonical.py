"""Canonical type definitions for TunaCode CLI.

These are the target types for the architecture refactor. They provide:
- Single representation for each concept (no polymorphism)
- Frozen dataclasses for immutability
- Explicit structure (no ad-hoc dicts)

See docs/refactoring/architecture-refactor-plan.md for migration strategy.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# =============================================================================
# Message Types
# =============================================================================
# These replace the polymorphic message handling in the legacy content
# extraction and sanitize.py. One type, one accessor, no branching.


class MessageRole(Enum):
    """Role of a message in the conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class PartKind(Enum):
    """Discriminator for message part types."""

    TEXT = "text"
    TOOL_CALL = "tool-call"
    TOOL_RETURN = "tool-return"
    RETRY_PROMPT = "retry-prompt"
    SYSTEM_PROMPT = "system-prompt"
    THOUGHT = "thought"


@dataclass(frozen=True, slots=True)
class TextPart:
    """Plain text content in a message."""

    content: str
    kind: PartKind = field(default=PartKind.TEXT, repr=False)


@dataclass(frozen=True, slots=True)
class ThoughtPart:
    """Internal reasoning/thought content."""

    content: str
    kind: PartKind = field(default=PartKind.THOUGHT, repr=False)


@dataclass(frozen=True, slots=True)
class SystemPromptPart:
    """System prompt content."""

    content: str
    kind: PartKind = field(default=PartKind.SYSTEM_PROMPT, repr=False)


@dataclass(frozen=True, slots=True)
class ToolCallPart:
    """A tool invocation request from the assistant."""

    tool_call_id: str
    tool_name: str
    args: dict[str, Any]
    kind: PartKind = field(default=PartKind.TOOL_CALL, repr=False)


@dataclass(frozen=True, slots=True)
class ToolReturnPart:
    """Result returned from a tool execution."""

    tool_call_id: str
    content: str
    kind: PartKind = field(default=PartKind.TOOL_RETURN, repr=False)


# NOTE: retry prompts are emitted when a tool call fails and the model is re-prompted.
@dataclass(frozen=True, slots=True)
class RetryPromptPart:
    """Retry prompt emitted after a tool call failure."""

    tool_call_id: str
    tool_name: str
    content: str
    kind: PartKind = field(default=PartKind.RETRY_PROMPT, repr=False)


# Union of all part types for type hints
CanonicalPart = (
    TextPart | ThoughtPart | SystemPromptPart | ToolCallPart | ToolReturnPart | RetryPromptPart
)


@dataclass(frozen=True, slots=True)
class CanonicalMessage:
    """Canonical message representation.

    This is the single source of truth for message structure.
    All other formats (pydantic-ai, dict) are converted to/from this.
    """

    role: MessageRole
    parts: tuple[CanonicalPart, ...]
    timestamp: datetime | None = None

    def get_text_content(self) -> str:
        """Extract concatenated text content, preserving part boundaries."""
        text_segments: list[str] = []
        for part in self.parts:
            content_value = getattr(part, "content", "")
            content_text = "" if content_value is None else str(content_value)
            text_segments.append(content_text)
        return " ".join(text_segments)

    def get_tool_call_ids(self) -> set[str]:
        """Get all tool call IDs in this message."""
        return {p.tool_call_id for p in self.parts if isinstance(p, ToolCallPart)}

    def get_tool_return_ids(self) -> set[str]:
        """Get all tool return IDs in this message."""
        return {p.tool_call_id for p in self.parts if isinstance(p, ToolReturnPart)}


# =============================================================================
# Tool Call Types
# =============================================================================
# These replace the duplicated tracking in session.runtime.tool_registry
# and message parts.


class ToolCallStatus(Enum):
    """Lifecycle status of a tool call."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class CanonicalToolCall:
    """Typed tool call record.

    Single source of truth for tool call state.
    Replaces session.runtime tool call tracking and argument caches.
    """

    tool_call_id: str
    tool_name: str
    args: dict[str, Any]
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        """Check if tool call has finished (success or failure)."""
        return self.status in (
            ToolCallStatus.COMPLETED,
            ToolCallStatus.FAILED,
            ToolCallStatus.CANCELLED,
        )


# =============================================================================
# Usage Types
# =============================================================================
# These complement existing TokenUsage/CostBreakdown in dataclasses.py


@dataclass(slots=True)
class UsageMetrics:
    """API usage metrics for a single call or cumulative session.

    Replaces ad-hoc dicts like {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost: float = 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens used (prompt + completion)."""
        return self.prompt_tokens + self.completion_tokens

    def add(self, other: "UsageMetrics") -> None:
        """Accumulate usage from another metrics object."""
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.cached_tokens += other.cached_tokens
        self.cost += other.cost

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UsageMetrics":
        """Convert from legacy dict format."""
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            cached_tokens=data.get("cached_tokens", 0),
            cost=data.get("cost", 0.0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to legacy dict format for backward compatibility."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cached_tokens": self.cached_tokens,
            "cost": self.cost,
        }


# =============================================================================
# Recursive Context Types
# =============================================================================
# These replace recursive_context_stack: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class RecursiveContext:
    """Context for nested/recursive agent execution.

    Replaces ad-hoc dicts in recursive_context_stack.
    """

    task_id: str
    parent_task_id: str | None
    depth: int
    iteration_budget: int
    created_at: datetime


# =============================================================================
# Normalized Usage Types (from pydantic_ai.py migration)
# =============================================================================
# These provide a framework-agnostic shape for extracting usage from
# any provider's response object.

DEFAULT_TOKEN_COUNT = 0
USAGE_ATTR_REQUEST_TOKENS = "request_tokens"
USAGE_ATTR_RESPONSE_TOKENS = "response_tokens"
USAGE_ATTR_CACHED_TOKENS = "cached_tokens"


@dataclass(frozen=True, slots=True)
class NormalizedUsage:
    """Normalized usage values for provider-agnostic tracking.

    This provides a stable shape for extracting token counts from
    various LLM provider response objects.
    """

    request_tokens: int
    response_tokens: int
    cached_tokens: int


def _read_usage_value(usage: Any, attribute: str) -> int:
    """Read a usage attribute, defaulting to 0 if not present."""
    raw_value = getattr(usage, attribute, None)
    return int(raw_value or DEFAULT_TOKEN_COUNT)


def normalize_request_usage(usage: Any | None) -> NormalizedUsage | None:
    """Normalize usage objects to a stable shape for internal tracking.

    Works with any object that has request_tokens, response_tokens, and
    cached_tokens attributes (e.g., pydantic-ai Usage objects).
    """
    if usage is None:
        return None

    return NormalizedUsage(
        request_tokens=_read_usage_value(usage, USAGE_ATTR_REQUEST_TOKENS),
        response_tokens=_read_usage_value(usage, USAGE_ATTR_RESPONSE_TOKENS),
        cached_tokens=_read_usage_value(usage, USAGE_ATTR_CACHED_TOKENS),
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Message types
    "MessageRole",
    "PartKind",
    "TextPart",
    "ThoughtPart",
    "SystemPromptPart",
    "ToolCallPart",
    "ToolReturnPart",
    "RetryPromptPart",
    "CanonicalPart",
    "CanonicalMessage",
    # Tool call types
    "ToolCallStatus",
    "CanonicalToolCall",
    # Usage types
    "UsageMetrics",
    # Recursive context types
    "RecursiveContext",
    # Normalized usage types
    "NormalizedUsage",
    "normalize_request_usage",
]
