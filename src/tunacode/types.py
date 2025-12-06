"""
Centralized type definitions for TunaCode CLI.

This module contains all type aliases, protocols, and type definitions
used throughout the TunaCode codebase.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    Union,
)

from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ToolReturnPart

PydanticAgent = Agent
MessagePart = Union[ToolReturnPart, Any]
ModelRequest = ModelRequest  # type: ignore[misc]
ModelResponse = Any


UserConfig = Dict[str, Any]
EnvConfig = Dict[str, str]
ModelName = str
ToolName = str
SessionId = str
DeviceId = str
InputSessions = Dict[str, Any]

LoggingConfig = Dict[str, Any]
LoggingEnabled = bool


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


ModelRegistry = Dict[str, ModelConfig]

ConfigPath = Path
ConfigFile = Path


ToolArgs = Dict[str, Any]
ToolResult = str
ToolCallback = Callable[[Any, Any], Awaitable[None]]
ToolStartCallback = Callable[[str], None]  # Called when tool execution starts
ToolCallId = str


class ToolFunction(Protocol):
    """Protocol for tool functions."""

    async def __call__(self, *_args, **kwargs) -> str: ...


@dataclass
class Template:
    """Represents a template with metadata and allowed tools."""

    name: str
    description: str
    prompt: str
    allowed_tools: List[str]
    parameters: Dict[str, str] = field(default_factory=dict)
    shortcut: Optional[str] = None


@dataclass
class ToolConfirmationRequest:
    """Request for tool execution confirmation."""

    tool_name: str
    args: Dict[str, Any]
    filepath: Optional[str] = None


@dataclass
class ToolConfirmationResponse:
    """Response from tool confirmation dialog."""

    approved: bool
    skip_future: bool = False
    abort: bool = False
    instructions: str = ""


class UILogger(Protocol):
    """Protocol for UI logging operations."""

    async def info(self, message: str) -> None: ...

    async def error(self, message: str) -> None: ...

    async def warning(self, message: str) -> None: ...

    async def debug(self, message: str) -> None: ...

    async def success(self, message: str) -> None: ...


UICallback = Callable[[str], Awaitable[None]]
UIInputCallback = Callable[[str, str], Awaitable[str]]

AgentResponse = Any
MessageHistory = List[Any]
AgentRun = Any

AgentConfig = Dict[str, Any]
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
    issues: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)


class AgentState(Enum):
    """Agent loop states for enhanced completion detection."""

    USER_INPUT = "user_input"  # Initial: user prompt received
    ASSISTANT = "assistant"  # Reasoning/deciding phase
    TOOL_EXECUTION = "tool_execution"  # Tool execution phase
    RESPONSE = "response"  # Handling results, may complete or loop


StateManager = Any

CommandArgs = List[str]
CommandResult = Optional[Any]
ProcessRequestCallback = Callable[[str, StateManager, bool], Awaitable[Any]]


@dataclass
class CommandContext:
    """Context passed to command handlers."""

    state_manager: StateManager
    process_request: Optional[ProcessRequestCallback] = None


FilePath = Union[str, Path]
FileContent = str
FileEncoding = str
FileDiff = Tuple[str, str]
FileSize = int
LineNumber = int

ErrorContext = Dict[str, Any]
OriginalError = Optional[Exception]
ErrorMessage = str

AsyncFunc = Callable[..., Awaitable[Any]]
AsyncToolFunc = Callable[..., Awaitable[str]]
AsyncVoidFunc = Callable[..., Awaitable[None]]

UpdateOperation = Dict[str, Any]
DiffLine = str
DiffHunk = List[DiffLine]

ValidationResult = Union[bool, str]
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
