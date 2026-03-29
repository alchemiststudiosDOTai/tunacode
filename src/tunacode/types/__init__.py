"""Centralized type definitions for TunaCode CLI.

This package contains all type aliases, protocols, and type definitions
used throughout the TunaCode codebase.

All types are re-exported from this module for backward compatibility.
"""

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
    LspSettings,
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

# Canonical types (new - see docs/refactoring/architecture-refactor-plan.md)
from tunacode.types.canonical import (  # noqa: F401
    CanonicalMessage,
    CanonicalPart,
    CanonicalToolCall,
    CanonicalToolResult,
    MessageRole,
    PartKind,
    RecursiveContext,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThoughtPart,
    ToolCallStatus,
    ToolResultContentKind,
    ToolResultImagePart,
    ToolResultTextPart,
    UsageMetrics,
)
from tunacode.types.canonical import (  # noqa: F401
    ToolCallPart as CanonicalToolCallPart,
)
from tunacode.types.canonical import (  # noqa: F401
    ToolReturnPart as CanonicalToolReturnPart,
)

# Dataclasses
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
