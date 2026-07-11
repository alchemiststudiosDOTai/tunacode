"""Base type aliases for TunaCode CLI."""

from pathlib import Path
from typing import TypeAlias, TypedDict

from tinyagent.agent_types import AgentToolResult, JsonObject

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
FileSize = int
LineNumber = int
ConfigPath = Path
ConfigFile = Path

# Configuration types


class RipgrepSettings(TypedDict):
    timeout: int
    max_results: int
    enable_metrics: bool


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


EnvConfig = dict[str, str]


class UserConfig(TypedDict):
    default_model: ModelName
    recent_models: list[ModelName]
    env: EnvConfig
    settings: UserSettings


# Tool types
ToolArgs: TypeAlias = JsonObject
ToolResult: TypeAlias = AgentToolResult

# Error handling types
OriginalError = Exception | None
ErrorMessage = str

# Token/Cost types
TokenCount = int
CostAmount = float
