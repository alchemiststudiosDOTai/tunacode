"""Centralized type definitions for TunaCode CLI.

This package contains all type aliases, protocols, and type definitions
used throughout the TunaCode codebase.

All types are re-exported from this module for backward compatibility.
"""

from collections.abc import Awaitable, Callable
from typing import Any

# Base types
from tunacode.types.base import (
    AgentConfig,
    AgentName,
    CommandArgs,
    CommandResult,
    ConfigFile,
    ConfigPath,
    CostAmount,
    DeviceId,
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
    ToolCallback,
    ToolProgress,
    ToolProgressCallback,
    ToolStartCallback,
    UICallback,
    UIInputCallback,
)

# Dataclasses
from tunacode.types.dataclasses import (
    AgentState,
    CommandContext,
    CostBreakdown,
    FallbackResponse,
    ModelConfig,
    ModelPricing,
    ModelRegistry,
    ResponseState,
    TokenUsage,
    ToolConfirmationRequest,
    ToolConfirmationResponse,
)

# Pydantic-AI wrappers
from tunacode.types.pydantic_ai import (
    AgentResponse,
    AgentRun,
    MessageHistory,
    MessagePart,
    ModelRequest,
    ModelResponse,
    PydanticAgent,
)

# State protocol
from tunacode.types.state import (
    SessionStateProtocol,
    StateManagerProtocol,
)

# ProcessRequestCallback uses the protocol, not concrete implementation
ProcessRequestCallback = Callable[[str, StateManagerProtocol, bool], Awaitable[Any]]

__all__ = [
    # Base types
    "AgentConfig",
    "AgentName",
    "CommandArgs",
    "CommandResult",
    "ConfigFile",
    "ConfigPath",
    "CostAmount",
    "DeviceId",
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
    # Pydantic-AI
    "AgentResponse",
    "AgentRun",
    "MessageHistory",
    "MessagePart",
    "ModelRequest",
    "ModelResponse",
    "PydanticAgent",
    # Callbacks
    "AsyncFunc",
    "AsyncToolFunc",
    "AsyncVoidFunc",
    "ProcessRequestCallback",
    "ToolCallback",
    "ToolProgress",
    "ToolProgressCallback",
    "ToolStartCallback",
    "UICallback",
    "UIInputCallback",
    # State
    "SessionStateProtocol",
    "StateManagerProtocol",
    # Dataclasses
    "AgentState",
    "CommandContext",
    "CostBreakdown",
    "FallbackResponse",
    "ModelConfig",
    "ModelPricing",
    "ModelRegistry",
    "ResponseState",
    "TokenUsage",
    "ToolConfirmationRequest",
    "ToolConfirmationResponse",
]
