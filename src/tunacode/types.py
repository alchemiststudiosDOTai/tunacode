"""
Centralized type definitions for TunaCode CLI.

This module contains all type aliases, protocols, and type definitions
used throughout the TunaCode codebase.
"""

from dataclasses import dataclass, field
from datetime import datetime

# Plan types will be defined below
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    Tuple,
    Union,
)

# Import pydantic-ai types (required dependency)
from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ToolReturnPart

PydanticAgent = Agent
MessagePart = Union[ToolReturnPart, Any]
ModelRequest = ModelRequest  # type: ignore[misc]
ModelResponse = Any


@dataclass
class TodoItem:
    id: str
    content: str
    status: Literal["pending", "in_progress", "completed"]
    priority: Literal["high", "medium", "low"]
    created_at: datetime
    completed_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)


# =============================================================================
# Core Types
# =============================================================================

# Basic type aliases
UserConfig = Dict[str, Any]
EnvConfig = Dict[str, str]
ModelName = str
ToolName = str
SessionId = str
DeviceId = str
InputSessions = Dict[str, Any]

# Logging configuration types
LoggingConfig = Dict[str, Any]
LoggingEnabled = bool

# =============================================================================
# Configuration Types
# =============================================================================


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

# Path configuration
ConfigPath = Path
ConfigFile = Path

# =============================================================================
# Tool Types
# =============================================================================

# Tool execution types
ToolArgs = Dict[str, Any]
ToolResult = str
ToolCallback = Callable[[Any, Any], Awaitable[None]]
ToolCallId = str


class ToolFunction(Protocol):
    """Protocol for tool functions."""

    async def __call__(self, *_args, **kwargs) -> str: ...


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


# =============================================================================
# UI Types
# =============================================================================


class UILogger(Protocol):
    """Protocol for UI logging operations."""

    async def info(self, message: str) -> None: ...

    async def error(self, message: str) -> None: ...

    async def warning(self, message: str) -> None: ...

    async def debug(self, message: str) -> None: ...

    async def success(self, message: str) -> None: ...


# UI callback types
UICallback = Callable[[str], Awaitable[None]]
UIInputCallback = Callable[[str, str], Awaitable[str]]

# =============================================================================
# Agent Types
# =============================================================================

# Agent response types
AgentResponse = Any  # Replace with proper pydantic-ai types when available
MessageHistory = List[Any]
AgentRun = Any  # pydantic_ai.RunContext or similar

# Agent configuration
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


@dataclass
class SimpleResult:
    """Simple result container for agent responses."""

    output: str


# =============================================================================
# Plan Types
# =============================================================================


class PlanPhase(Enum):
    """Plan Mode phases."""

    PLANNING_RESEARCH = "research"
    PLANNING_DRAFT = "draft"
    PLAN_READY = "ready"
    REVIEW_DECISION = "review"


class AgentState(Enum):
    """Agent loop states for enhanced completion detection."""

    USER_INPUT = "user_input"  # Initial: user prompt received
    ASSISTANT = "assistant"  # Reasoning/deciding phase
    TOOL_EXECUTION = "tool_execution"  # Tool execution phase
    RESPONSE = "response"  # Handling results, may complete or loop


@dataclass
class PlanDoc:
    """Structured plan document with all required sections."""

    # Required sections
    title: str
    overview: str
    steps: List[str]
    files_to_modify: List[str]
    files_to_create: List[str]

    # Optional but recommended sections
    risks: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    rollback: Optional[str] = None
    open_questions: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the plan document.

        Returns:
            tuple: (is_valid, list_of_missing_sections)
        """
        missing = []

        # Check required fields
        if not self.title or not self.title.strip():
            missing.append("title")
        if not self.overview or not self.overview.strip():
            missing.append("overview")
        if not self.steps:
            missing.append("steps")
        if not self.files_to_modify and not self.files_to_create:
            missing.append("files_to_modify or files_to_create")

        return len(missing) == 0, missing


# =============================================================================
# Session and State Types
# =============================================================================


@dataclass
class SessionState:
    """Complete session state for the application."""

    user_config: Dict[str, Any]
    agents: Dict[str, Any]
    messages: List[Any]
    total_cost: float
    current_model: str
    spinner: Optional[Any]
    tool_ignore: List[str]
    yolo: bool
    undo_initialized: bool
    session_id: str
    device_id: Optional[str]
    input_sessions: Dict[str, Any]
    current_task: Optional[Any]


# Forward reference for StateManager to avoid circular imports
StateManager = Any  # Will be replaced with actual StateManager type

# =============================================================================
# Command Types
# =============================================================================

# Command execution types
CommandArgs = List[str]
CommandResult = Optional[Any]
ProcessRequestCallback = Callable[[str, StateManager, bool], Awaitable[Any]]


@dataclass
class CommandContext:
    """Context passed to command handlers."""

    state_manager: StateManager
    process_request: Optional[ProcessRequestCallback] = None


# =============================================================================
# Service Types
# =============================================================================

# MCP (Model Context Protocol) types
MCPServerConfig = Dict[str, Any]
MCPServers = Dict[str, MCPServerConfig]


# =============================================================================
# File Operation Types
# =============================================================================

# File-related types
FilePath = Union[str, Path]
FileContent = str
FileEncoding = str
FileDiff = Tuple[str, str]  # (original, modified)
FileSize = int
LineNumber = int

# =============================================================================
# Error Handling Types
# =============================================================================

# Error context types
ErrorContext = Dict[str, Any]
OriginalError = Optional[Exception]
ErrorMessage = str

# =============================================================================
# Async Types
# =============================================================================

# Async function types
AsyncFunc = Callable[..., Awaitable[Any]]
AsyncToolFunc = Callable[..., Awaitable[str]]
AsyncVoidFunc = Callable[..., Awaitable[None]]

# =============================================================================
# Diff and Update Types
# =============================================================================

# Types for file updates and diffs
UpdateOperation = Dict[str, Any]
DiffLine = str
DiffHunk = List[DiffLine]

# =============================================================================
# Validation Types
# =============================================================================

# Input validation types
ValidationResult = Union[bool, str]  # True for valid, error message for invalid
Validator = Callable[[Any], ValidationResult]

# =============================================================================
# Cost Tracking Types
# =============================================================================

# Cost calculation types
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


class UsageTrackerProtocol(Protocol):
    """Protocol for a class that tracks and displays token usage and cost."""

    async def track_and_display(self, response_obj: Any) -> None: ...
