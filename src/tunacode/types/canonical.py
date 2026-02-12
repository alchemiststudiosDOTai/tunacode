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
class UsageCost:
    """Cost breakdown aligned with tinyagent usage contract."""

    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0
    total: float = 0.0

    def add(self, other: "UsageCost") -> None:
        """Accumulate cost from another usage cost object."""
        self.input += other.input
        self.output += other.output
        self.cache_read += other.cache_read
        self.cache_write += other.cache_write
        self.total += other.total

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UsageCost":
        """Build cost object from canonical usage payload."""
        if not isinstance(data, dict):
            raise ValueError("usage.cost must be a dict")

        required_keys = frozenset({"input", "output", "cache_read", "cache_write", "total"})
        missing_keys = sorted(required_keys.difference(data.keys()))
        if missing_keys:
            raise ValueError(f"usage.cost missing key(s): {', '.join(missing_keys)}")

        return cls(
            input=float(data["input"]),
            output=float(data["output"]),
            cache_read=float(data["cache_read"]),
            cache_write=float(data["cache_write"]),
            total=float(data["total"]),
        )

    def to_dict(self) -> dict[str, float]:
        """Convert cost object to canonical usage payload."""
        return {
            "input": self.input,
            "output": self.output,
            "cache_read": self.cache_read,
            "cache_write": self.cache_write,
            "total": self.total,
        }


@dataclass(slots=True)
class UsageMetrics:
    """API usage metrics for a single call or cumulative session.

    Replaces ad-hoc dicts like {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
    """

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total_tokens: int = 0
    cost: UsageCost = field(default_factory=UsageCost)

    def add(self, other: "UsageMetrics") -> None:
        """Accumulate usage from another metrics object."""
        self.input += other.input
        self.output += other.output
        self.cache_read += other.cache_read
        self.cache_write += other.cache_write
        self.total_tokens += other.total_tokens
        self.cost.add(other.cost)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UsageMetrics":
        """Convert from canonical usage dict format."""
        if not isinstance(data, dict):
            raise ValueError("usage must be a dict")

        required_keys = frozenset(
            {"input", "output", "cache_read", "cache_write", "total_tokens", "cost"}
        )
        missing_keys = sorted(required_keys.difference(data.keys()))
        if missing_keys:
            raise ValueError(f"usage missing key(s): {', '.join(missing_keys)}")

        cost_raw = data["cost"]

        return cls(
            input=int(data["input"]),
            output=int(data["output"]),
            cache_read=int(data["cache_read"]),
            cache_write=int(data["cache_write"]),
            total_tokens=int(data["total_tokens"]),
            cost=UsageCost.from_dict(cost_raw),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to canonical usage dict format."""
        return {
            "input": self.input,
            "output": self.output,
            "cache_read": self.cache_read,
            "cache_write": self.cache_write,
            "total_tokens": self.total_tokens,
            "cost": self.cost.to_dict(),
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
    "UsageCost",
    "UsageMetrics",
    # Recursive context types
    "RecursiveContext",
]
