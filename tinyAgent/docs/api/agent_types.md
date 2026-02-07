# Agent Types Module

Type definitions for the agent framework. Uses TypedDict for runtime flexibility with type safety.

## Content Types

### TextContent
```python
class TextContent(TypedDict, total=False):
    type: Literal["text"]
    text: str
    text_signature: str | None
```
Text block in a message.

### ImageContent
```python
class ImageContent(TypedDict, total=False):
    type: Literal["image"]
    url: str
    mime_type: str | None
```
Image block (for vision models).

### ThinkingContent
```python
class ThinkingContent(TypedDict, total=False):
    type: Literal["thinking"]
    thinking: str
    thinking_signature: str | None
```
Reasoning/thinking block (for models like Claude 3.7).

### ToolCallContent
```python
class ToolCallContent(TypedDict, total=False):
    type: Literal["tool_call"]
    id: str
    name: str
    arguments: JsonObject
    partial_json: str
```
Tool invocation block. `partial_json` is used during streaming.

## Message Types

### UserMessage
```python
class UserMessage(TypedDict, total=False):
    role: Literal["user"]
    content: list[TextContent | ImageContent]
    timestamp: int | None
```
Input from the user.

### AssistantMessage
```python
class AssistantMessage(TypedDict, total=False):
    role: Literal["assistant"]
    content: list[AssistantContent | None]
    stop_reason: StopReason | None
    timestamp: int | None
    api: str | None
    provider: str | None
    model: str | None
    usage: JsonObject | None
    error_message: str | None
```
Response from the LLM.

### ToolResultMessage
```python
class ToolResultMessage(TypedDict, total=False):
    role: Literal["tool_result"]
    tool_call_id: str
    tool_name: str
    content: list[TextContent | ImageContent]
    details: JsonObject
    is_error: bool
    timestamp: int | None
```
Result from executing a tool.

### Message
```python
Message = Union[UserMessage, AssistantMessage, ToolResultMessage]
```
LLM-compatible message types only.

### AgentMessage
```python
AgentMessage = Union[Message, CustomAgentMessage]
```
Internal message type that allows custom roles.

## Tool Types

### Tool
```python
@dataclass
class Tool:
    name: str = ""
    description: str = ""
    parameters: JsonObject = field(default_factory=dict)
```
Tool schema definition.

### AgentTool
```python
@dataclass
class AgentTool(Tool):
    label: str = ""
    execute: Callable[..., Awaitable[AgentToolResult]] | None = None
```
Tool with execution function.

### AgentToolResult
```python
@dataclass
class AgentToolResult:
    content: list[TextContent | ImageContent] = field(default_factory=list)
    details: JsonObject = field(default_factory=dict)
```
Result from tool execution.

## Context Types

### Context
```python
@dataclass
class Context:
    system_prompt: str = ""
    messages: list[Message] = field(default_factory=list)
    tools: list[AgentTool] | None = None
```
LLM-compatible context.

### AgentContext
```python
@dataclass
class AgentContext:
    system_prompt: str = ""
    messages: list[AgentMessage] = field(default_factory=list)
    tools: list[AgentTool] | None = None
```
Internal context with AgentMessage support.

## Model Types

### ThinkingLevel
```python
class ThinkingLevel(str, Enum):
    OFF = "off"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
```
Reasoning level for supported models.

### Model
```python
@dataclass
class Model:
    provider: str = ""
    id: str = ""           # Model identifier
    api: str = ""          # API type (openai, anthropic, etc.)
    thinking_level: ThinkingLevel = ThinkingLevel.OFF
```
Model configuration.

### SimpleStreamOptions
```python
class SimpleStreamOptions(TypedDict, total=False):
    api_key: str | None
    temperature: float | None
    max_tokens: int | None
    signal: asyncio.Event | None
```
Standard options passed to stream functions.

## Event Types

### AgentStartEvent / AgentEndEvent
```python
@dataclass
class AgentStartEvent:
    type: Literal["agent_start"] = "agent_start"

@dataclass
class AgentEndEvent:
    type: Literal["agent_end"] = "agent_end"
    messages: list[AgentMessage] = field(default_factory=list)
```
Agent run lifecycle events.

### TurnStartEvent / TurnEndEvent
```python
@dataclass
class TurnStartEvent:
    type: Literal["turn_start"] = "turn_start"

@dataclass
class TurnEndEvent:
    type: Literal["turn_end"] = "turn_end"
    message: AgentMessage | None = None
    tool_results: list[ToolResultMessage] = field(default_factory=list)
```
Single turn lifecycle events.

### MessageStartEvent / MessageUpdateEvent / MessageEndEvent
```python
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
```
Message streaming events.

### ToolExecution Events
```python
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
```
Tool execution lifecycle events.

### AgentEvent
```python
AgentEvent = Union[
    AgentStartEvent, AgentEndEvent,
    TurnStartEvent, TurnEndEvent,
    MessageStartEvent, MessageUpdateEvent, MessageEndEvent,
    ToolExecutionStartEvent, ToolExecutionUpdateEvent, ToolExecutionEndEvent,
]
```
All agent event types.

## Configuration Types

### AgentLoopConfig
```python
@dataclass
class AgentLoopConfig:
    model: Model
    convert_to_llm: ConvertToLlmFn
    transform_context: TransformContextFn | None = None
    get_api_key: ApiKeyResolver | None = None
    get_steering_messages: AgentMessageProvider | None = None
    get_follow_up_messages: AgentMessageProvider | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
```
Configuration for the agent loop.

### AgentState
```python
class AgentState(TypedDict, total=False):
    system_prompt: str
    model: Model | None
    thinking_level: ThinkingLevel
    tools: list[AgentTool]
    messages: list[AgentMessage]
    is_streaming: bool
    stream_message: AgentMessage | None
    pending_tool_calls: set[str]
    error: str | None
```
Complete agent state snapshot.

## Protocol Types

### StreamFn
```python
StreamFn: TypeAlias = Callable[
    [Model, Context, SimpleStreamOptions],
    Awaitable["StreamResponse"]
]
```
Function signature for LLM streaming providers.

### StreamResponse
```python
class StreamResponse(Protocol):
    def result(self) -> Awaitable[AssistantMessage]: ...
    def __aiter__(self) -> AsyncIterator[AssistantMessageEvent]: ...
    async def __anext__(self) -> AssistantMessageEvent: ...
```
Protocol for streaming responses.

## Utility Types

### JsonValue / JsonObject
```python
JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
```
JSON-compatible type aliases.

### EventStream
```python
class EventStream:
    def __init__(
        self,
        is_end_event: Callable[[AgentEvent], bool],
        get_result: Callable[[AgentEvent], list[AgentMessage]],
    )

    def push(self, event: AgentEvent) -> None
    def end(self, result: list[AgentMessage]) -> None
    async def result(self) -> list[AgentMessage]
```
Async event stream that yields events and returns a final result.
