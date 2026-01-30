"""Centralized type definitions for TunaCode CLI.

This package contains all type aliases, protocols, and type definitions
used throughout the TunaCode codebase.

All types are re-exported from this module for backward compatibility.
"""

# Base types
from tunacode.types.base import (
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
    SessionId,
    TokenCount,
    ToolArgs,
    ToolCallId,
    ToolName,
    ToolResult,
    UpdateOperation,
    UserConfig,
    ValidationResult,
    Validator,
)

# Callback types
from tunacode.types.callbacks import (
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

# Canonical types (new - see docs/refactoring/architecture-refactor-plan.md)
from tunacode.types.canonical import (
    CanonicalMessage,
    CanonicalPart,
    CanonicalToolCall,
    MessageRole,
    NormalizedUsage,
    PartKind,
    RecursiveContext,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThoughtPart,
    ToolCallStatus,
    UsageMetrics,
    normalize_request_usage,
)
from tunacode.types.canonical import (
    ToolCallPart as CanonicalToolCallPart,
)
from tunacode.types.canonical import (
    ToolReturnPart as CanonicalToolReturnPart,
)

# Dataclasses
from tunacode.types.dataclasses import (
    CostBreakdown,
    ModelConfig,
    ModelPricing,
    ModelRegistry,
    TokenUsage,
)

__all__ = [
    # Base types
    "AgentConfig",
    "AgentName",
    "CommandArgs",
    "CommandResult",
    "ConfigFile",
    "ConfigPath",
    "CostAmount",
    "DiffHunk",
    "DiffLine",
    "EnvConfig",
    "ErrorContext",
    "ErrorMessage",
    "FileContent",
    "FileDiff",
    "FileEncoding",
    "FilePath",
    "FileSize",
    "InputSessions",
    "LineNumber",
    "ModelName",
    "OriginalError",
    "SessionId",
    "TokenCount",
    "ToolArgs",
    "ToolCallId",
    "ToolName",
    "ToolResult",
    "UpdateOperation",
    "UserConfig",
    "ValidationResult",
    "Validator",
    # Callbacks and protocols
    "AsyncFunc",
    "AsyncToolFunc",
    "AsyncVoidFunc",
    "NoticeCallback",
    "StreamingCallback",
    "StreamResultProtocol",
    "ToolCallback",
    "ToolCallPartProtocol",
    "ToolResultCallback",
    "ToolStartCallback",
    "UICallback",
    "UIInputCallback",
    # Dataclasses
    "CostBreakdown",
    "ModelConfig",
    "ModelPricing",
    "ModelRegistry",
    "TokenUsage",
    # Canonical types
    "CanonicalMessage",
    "CanonicalPart",
    "CanonicalToolCall",
    "CanonicalToolCallPart",
    "CanonicalToolReturnPart",
    "MessageRole",
    "NormalizedUsage",
    "PartKind",
    "RecursiveContext",
    "RetryPromptPart",
    "SystemPromptPart",
    "TextPart",
    "ThoughtPart",
    "ToolCallStatus",
    "UsageMetrics",
    "normalize_request_usage",
]
