"""Type definitions for the agent loop."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Protocol, TypeAlias, TypedDict, TypeVar, Union

# ------------------------------
# JSON-ish helper types
# ------------------------------

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


# ------------------------------
# Core message/content types
# ------------------------------


class ThinkingBudgets(TypedDict, total=False):
    """Token budgets for thinking/reasoning."""

    thinking_budget: int
    max_tokens: int


TResult = TypeVar("TResult")

MaybeAwaitable: TypeAlias = TResult | Awaitable[TResult]


class ThinkingLevel(str, Enum):
    """Thinking/reasoning level for models that support it."""

    OFF = "off"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


class TextContent(TypedDict, total=False):
    """Text content block."""

    type: Literal["text"]
    text: str
    text_signature: str | None


class ImageContent(TypedDict, total=False):
    """Image content block."""

    type: Literal["image"]
    url: str
    mime_type: str | None


class ThinkingContent(TypedDict, total=False):
    """Thinking content block."""

    type: Literal["thinking"]
    thinking: str
    thinking_signature: str | None


class ToolCallContent(TypedDict, total=False):
    """Tool call content block."""

    type: Literal["tool_call"]
    id: str
    name: str
    arguments: JsonObject
    partial_json: str


ToolCall: TypeAlias = ToolCallContent

AssistantContent: TypeAlias = TextContent | ThinkingContent | ToolCallContent


class UserMessage(TypedDict, total=False):
    """User message for LLM."""

    role: Literal["user"]
    content: list[TextContent | ImageContent]
    timestamp: int | None


StopReason: TypeAlias = Literal[
    "complete",
    "error",
    "aborted",
    "tool_calls",
    "stop",
    "length",
    "tool_use",
]


class AssistantMessage(TypedDict, total=False):
    """Assistant message from LLM."""

    role: Literal["assistant"]
    content: list[AssistantContent | None]
    stop_reason: StopReason | None
    timestamp: int | None
    api: str | None
    provider: str | None
    model: str | None
    usage: JsonObject | None
    error_message: str | None


class ToolResultMessage(TypedDict, total=False):
    """Tool result message."""

    role: Literal["tool_result"]
    tool_call_id: str
    tool_name: str
    content: list[TextContent | ImageContent]
    details: JsonObject
    is_error: bool
    timestamp: int | None


Message = Union[UserMessage, AssistantMessage, ToolResultMessage]


class CustomAgentMessage(TypedDict, total=False):
    """Base class for custom agent messages."""

    role: str
    timestamp: int | None


AgentMessage = Union[Message, CustomAgentMessage]


ConvertToLlmFn: TypeAlias = Callable[[list[AgentMessage]], MaybeAwaitable[list[Message]]]
TransformContextFn: TypeAlias = Callable[
    [list[AgentMessage], asyncio.Event | None],
    Awaitable[list[AgentMessage]],
]
ApiKeyResolver: TypeAlias = Callable[[str], MaybeAwaitable[str | None]]
AgentMessageProvider: TypeAlias = Callable[[], Awaitable[list[AgentMessage]]]


# ------------------------------
# Tool types
# ------------------------------


@dataclass
class AgentToolResult:
    """Result from executing a tool."""

    content: list[TextContent | ImageContent] = field(default_factory=list)
    details: JsonObject = field(default_factory=dict)


AgentToolUpdateCallback = Callable[[AgentToolResult], None]


@dataclass
class Tool:
    """Tool definition."""

    name: str = ""
    description: str = ""
    parameters: JsonObject = field(default_factory=dict)


@dataclass
class AgentTool(Tool):
    """Agent tool with execute function."""

    label: str = ""
    execute: Callable[..., Awaitable[AgentToolResult]] | None = None


# ------------------------------
# Context/model types
# ------------------------------


@dataclass
class Context:
    """Context for LLM calls."""

    system_prompt: str = ""
    messages: list[Message] = field(default_factory=list)
    tools: list[AgentTool] | None = None


@dataclass
class AgentContext:
    """Agent context with AgentMessage types."""

    system_prompt: str = ""
    messages: list[AgentMessage] = field(default_factory=list)
    tools: list[AgentTool] | None = None


@dataclass
class Model:
    """Model configuration."""

    provider: str = ""
    id: str = ""  # Model identifier (e.g., "gpt-4", "claude-3.5-sonnet")
    api: str = ""  # API type (e.g., "openai", "anthropic", "openrouter")
    thinking_level: ThinkingLevel = ThinkingLevel.OFF


class SimpleStreamOptions(TypedDict, total=False):
    """Standard stream options passed to providers."""

    api_key: str | None
    temperature: float | None
    max_tokens: int | None
    signal: asyncio.Event | None


StreamFn: TypeAlias = Callable[[Model, Context, SimpleStreamOptions], Awaitable["StreamResponse"]]


class AssistantMessageEvent(TypedDict, total=False):
    """Event during assistant message streaming."""

    type: Literal[
        "start",
        "text_start",
        "text_delta",
        "text_end",
        "thinking_start",
        "thinking_delta",
        "thinking_end",
        "tool_call_start",
        "tool_call_delta",
        "tool_call_end",
        "done",
        "error",
    ]
    partial: AssistantMessage | None
    content_index: int
    delta: str
    content: str | TextContent | ThinkingContent | ToolCallContent | None
    tool_call: ToolCallContent | None
    reason: str
    message: AssistantMessage | None
    error: AssistantMessage | str | None


class StreamResponse(Protocol):
    """Response from streaming."""

    def result(self) -> Awaitable[AssistantMessage]: ...

    def __aiter__(self) -> AsyncIterator[AssistantMessageEvent]: ...

    async def __anext__(self) -> AssistantMessageEvent: ...


# ------------------------------
# Agent event types
# ------------------------------


@dataclass
class AgentStartEvent:
    type: Literal["agent_start"] = "agent_start"


@dataclass
class AgentEndEvent:
    type: Literal["agent_end"] = "agent_end"
    messages: list[AgentMessage] = field(default_factory=list)


@dataclass
class TurnStartEvent:
    type: Literal["turn_start"] = "turn_start"


@dataclass
class TurnEndEvent:
    type: Literal["turn_end"] = "turn_end"
    message: AgentMessage | None = None
    tool_results: list[ToolResultMessage] = field(default_factory=list)


@dataclass
class MessageStartEvent:
    type: Literal["message_start"] = "message_start"
    message: AgentMessage | None = None


@dataclass
class MessageUpdateEvent:
    type: Literal["message_update"] = "message_update"
    message: AgentMessage | None = None
    assistant_message_event: AssistantMessageEvent | None = None


@dataclass
class MessageEndEvent:
    type: Literal["message_end"] = "message_end"
    message: AgentMessage | None = None


@dataclass
class ToolExecutionStartEvent:
    type: Literal["tool_execution_start"] = "tool_execution_start"
    tool_call_id: str = ""
    tool_name: str = ""
    args: JsonObject | None = None


@dataclass
class ToolExecutionUpdateEvent:
    type: Literal["tool_execution_update"] = "tool_execution_update"
    tool_call_id: str = ""
    tool_name: str = ""
    args: JsonObject | None = None
    partial_result: AgentToolResult | None = None


@dataclass
class ToolExecutionEndEvent:
    type: Literal["tool_execution_end"] = "tool_execution_end"
    tool_call_id: str = ""
    tool_name: str = ""
    result: AgentToolResult | None = None
    is_error: bool = False


AgentEvent = Union[
    AgentStartEvent,
    AgentEndEvent,
    TurnStartEvent,
    TurnEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    MessageEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolExecutionEndEvent,
]


@dataclass
class AgentLoopConfig:
    """Configuration for the agent loop."""

    model: Model
    convert_to_llm: ConvertToLlmFn
    transform_context: TransformContextFn | None = None
    get_api_key: ApiKeyResolver | None = None
    get_steering_messages: AgentMessageProvider | None = None
    get_follow_up_messages: AgentMessageProvider | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class AgentState(TypedDict, total=False):
    """Agent state containing all configuration and conversation data."""

    system_prompt: str
    model: Model | None
    thinking_level: ThinkingLevel
    tools: list[AgentTool]
    messages: list[AgentMessage]
    is_streaming: bool
    stream_message: AgentMessage | None
    pending_tool_calls: set[str]
    error: str | None


class EventStream:
    """Async event stream that yields events and returns a final result."""

    def __init__(
        self,
        is_end_event: Callable[[AgentEvent], bool],
        get_result: Callable[[AgentEvent], list[AgentMessage]],
    ):
        self._queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._is_end_event = is_end_event
        self._get_result = get_result
        self._result: list[AgentMessage] | None = None
        self._ended = False

    def push(self, event: AgentEvent) -> None:
        if self._ended:
            return
        self._queue.put_nowait(event)

    def end(self, result: list[AgentMessage]) -> None:
        self._result = result
        self._ended = True

    def __aiter__(self):
        return self

    async def __anext__(self) -> AgentEvent:
        if self._ended and self._queue.empty():
            raise StopAsyncIteration

        event = await self._queue.get()
        if self._is_end_event(event):
            self._result = self._get_result(event)
            self._ended = True
        return event

    async def result(self) -> list[AgentMessage]:
        while not self._ended:
            try:
                await self.__anext__()
            except StopAsyncIteration:
                break

        return self._result or []
