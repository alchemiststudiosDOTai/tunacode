"""Centralized type definitions for TunaCode CLI.

This package contains all type aliases, protocols, and type definitions
used throughout the TunaCode codebase.

All types are re-exported from this module for backward compatibility.
"""

from dataclasses import dataclass, field
from typing import Any

# Base types
from tunacode.types.base import (  # noqa: F401
    AgentConfig,
    AgentName,
    CommandArgs,
    CommandResult,
    ConfigFile,
    ConfigPath,
    CostAmount,
    DiffHunk,
    DiffLine,
    EnvConfig,
    ErrorContext,
    ErrorMessage,
    FileContent,
    FileDiff,
    FileEncoding,
    FilePath,
    FileSize,
    InputSessions,
    LineNumber,
    ModelName,
    OriginalError,
    RipgrepSettings,
    SessionId,
    TokenCount,
    ToolArgs,
    ToolCallId,
    ToolName,
    ToolResult,
    UpdateOperation,
    UserConfig,
    UserSettings,
    ValidationResult,
    Validator,
)

# Callback types
from tunacode.types.callbacks import (  # noqa: F401
    AsyncFunc,
    AsyncToolFunc,
    AsyncVoidFunc,
    NoticeCallback,
    StreamingCallback,
    StreamResultProtocol,
    ToolCallback,
    ToolCallPartProtocol,
    ToolResultCallback,
    ToolStartCallback,
    UICallback,
    UIInputCallback,
)
from tunacode.types.dataclasses import (  # noqa: F401
    CostBreakdown,
    ModelPricing,
    TokenUsage,
)
from tunacode.types.models_registry import (  # noqa: F401
    ModelConfig,
    ModelRegistry,
    ModelsRegistryDocument,
    RegistryCostBreakdown,
    RegistryInterleavedConfig,
    RegistryModalities,
    RegistryModelCost,
    RegistryModelEntry,
    RegistryModelLimit,
    RegistryProviderEntry,
    RegistryProviderOverride,
)


@dataclass(slots=True)
class UsageCost:
    """Cost breakdown aligned with the tinyagent usage payload."""

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
        """Build cost object from a usage payload."""
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
        """Convert cost object to a usage payload."""
        return {
            "input": self.input,
            "output": self.output,
            "cache_read": self.cache_read,
            "cache_write": self.cache_write,
            "total": self.total,
        }


@dataclass(slots=True)
class UsageMetrics:
    """API usage metrics for a single call or cumulative session."""

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
        """Convert from a usage dict payload."""
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
        """Convert to a usage dict payload."""
        return {
            "input": self.input,
            "output": self.output,
            "cache_read": self.cache_read,
            "cache_write": self.cache_write,
            "total_tokens": self.total_tokens,
            "cost": self.cost.to_dict(),
        }
