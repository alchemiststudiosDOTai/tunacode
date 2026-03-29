"""Base type aliases for TunaCode CLI."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeAlias, TypedDict

from tinyagent.agent_types import AgentToolResult

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


class RipgrepSettings(TypedDict):
    timeout: int
    max_results: int
    enable_metrics: bool


class LspSettings(TypedDict):
    enabled: bool
    timeout: float


class UserSettings(TypedDict):
    max_retries: int
    max_iterations: int
    request_delay: float
    global_request_timeout: float
    tool_strict_validation: bool
    theme: str
    stream_agent_text: bool
    max_command_output: int
    max_tokens: int | None
    ripgrep: RipgrepSettings
    lsp: LspSettings


EnvConfig = dict[str, str]


class UserConfig(TypedDict):
    default_model: ModelName
    recent_models: list[ModelName]
    env: EnvConfig
    settings: UserSettings


InputSessions = dict[str, Any]
AgentConfig = dict[str, Any]

# Tool types
ToolArgs = dict[str, Any]
ToolResult: TypeAlias = AgentToolResult

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
