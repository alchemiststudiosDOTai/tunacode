"""Base type aliases for TunaCode CLI.

Contains fundamental type definitions that have no external dependencies
beyond Python stdlib.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

# Identity types - string wrappers for semantic clarity
ModelName = str
ToolName = str
SessionId = str
AgentName = str
ToolCallId = str

# File system types
FilePath = str | Path
FileContent = str
FileEncoding = str
FileDiff = tuple[str, str]
FileSize = int
LineNumber = int
ConfigPath = Path
ConfigFile = Path

# Configuration types
UserConfig = dict[str, Any]
EnvConfig = dict[str, str]
InputSessions = dict[str, Any]
AgentConfig = dict[str, Any]

# Tool types
ToolArgs = dict[str, Any]
ToolResult = str

# Error handling types
ErrorContext = dict[str, Any]
OriginalError = Exception | None
ErrorMessage = str

# Diff types
UpdateOperation = dict[str, Any]
DiffLine = str
DiffHunk = list[DiffLine]

# Validation types
ValidationResult = bool | str
Validator = Callable[[Any], ValidationResult]

# Token/Cost types
TokenCount = int
CostAmount = float

# Command types
CommandArgs = list[str]
CommandResult = Any | None

__all__ = [
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
]
