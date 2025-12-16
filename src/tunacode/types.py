"""
Centralized type definitions for TunaCode CLI.

This module contains all type aliases, protocols, and type definitions
used throughout the TunaCode codebase.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Protocol,
)

from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ToolReturnPart

PydanticAgent = Agent
MessagePart = ToolReturnPart | Any
ModelRequest = ModelRequest  # type: ignore[misc]
ModelResponse = Any


UserConfig = dict[str, Any]
EnvConfig = dict[str, str]
ModelName = str
ToolName = str
SessionId = str
DeviceId = str
InputSessions = dict[str, Any]


@dataclass
class ModelPricing:
    """Pricing information for a model."""

    input: float
    cached_input: float
    output: float


@dataclass
class ModelConfig:
    """Configuration for a model including pricing."""

    pricing: ModelPricing


ModelRegistry = dict[str, ModelConfig]

ConfigPath = Path
ConfigFile = Path


ToolArgs = dict[str, Any]
ToolResult = str
ToolCallback = Callable[[Any, Any], Awaitable[None]]
ToolStartCallback = Callable[[str], None]  # Called when tool execution starts
ToolProgressCallback = Callable[[str, str, int, int], None]  # (subagent, operation, current, total)
ToolCallId = str


class ToolFunction(Protocol):
    """Protocol for tool functions."""

    async def __call__(self, *_args, **kwargs) -> str: ...


@dataclass
class ToolConfirmationRequest:
    """Request for tool execution confirmation."""

    tool_name: str
    args: dict[str, Any]
    filepath: str | None = None
    diff_content: str | None = None


@dataclass
class ToolConfirmationResponse:
    """Response from tool confirmation dialog."""

    approved: bool
    skip_future: bool = False
    abort: bool = False
    instructions: str = ""


UICallback = Callable[[str], Awaitable[None]]
UIInputCallback = Callable[[str, str], Awaitable[str]]

AgentResponse = Any
MessageHistory = list[Any]
AgentRun = Any

AgentConfig = dict[str, Any]
AgentName = str


@dataclass
class ResponseState:
    """Track whether a user visible response was produced."""

    has_user_response: bool = False
    has_final_synthesis: bool = False
    task_completed: bool = False
    awaiting_user_guidance: bool = False


@dataclass
class FallbackResponse:
    """Structure for synthesized fallback responses."""

    summary: str
    progress: str = ""
    issues: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


class AgentState(Enum):
    """Agent loop states for enhanced completion detection."""

    USER_INPUT = "user_input"  # Initial: user prompt received
    ASSISTANT = "assistant"  # Reasoning/deciding phase
    TOOL_EXECUTION = "tool_execution"  # Tool execution phase
    RESPONSE = "response"  # Handling results, may complete or loop


StateManager = Any

CommandArgs = list[str]
CommandResult = Any | None
ProcessRequestCallback = Callable[[str, StateManager, bool], Awaitable[Any]]


@dataclass
class CommandContext:
    """Context passed to command handlers."""

    state_manager: StateManager
    process_request: ProcessRequestCallback | None = None


FilePath = str | Path
FileContent = str
FileEncoding = str
FileDiff = tuple[str, str]
FileSize = int
LineNumber = int

ErrorContext = dict[str, Any]
OriginalError = Exception | None
ErrorMessage = str

AsyncFunc = Callable[..., Awaitable[Any]]
AsyncToolFunc = Callable[..., Awaitable[str]]
AsyncVoidFunc = Callable[..., Awaitable[None]]

UpdateOperation = dict[str, Any]
DiffLine = str
DiffHunk = list[DiffLine]

ValidationResult = bool | str
Validator = Callable[[Any], ValidationResult]

TokenCount = int
CostAmount = float


@dataclass
class TokenUsage:
    """Token usage for a request."""

    input_tokens: int
    cached_tokens: int
    output_tokens: int


@dataclass
class CostBreakdown:
    """Breakdown of costs for a request."""

    input_cost: float
    cached_cost: float
    output_cost: float
    total_cost: float
