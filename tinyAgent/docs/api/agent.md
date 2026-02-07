# Agent Module

High-level Agent class that wraps the agent loop with state management.

## Agent

```python
class Agent:
    def __init__(self, opts: AgentOptions | None = None)
```

The main agent class. Manages conversation state, event subscription, and provides synchronous-style methods for interaction.

### Configuration Methods

#### set_system_prompt
```python
def set_system_prompt(self, value: str) -> None
```
Set the system prompt sent to the LLM.

#### set_model
```python
def set_model(self, model: Model) -> None
```
Configure the LLM model to use.

#### set_thinking_level
```python
def set_thinking_level(self, level: ThinkingLevel) -> None
```
Set reasoning level (OFF, MINIMAL, LOW, MEDIUM, HIGH, XHIGH).

#### set_tools
```python
def set_tools(self, tools: list[AgentTool]) -> None
```
Set available tools the LLM can invoke.

### Prompt Methods

#### prompt
```python
async def prompt(
    self,
    input_data: str | AgentMessage | list[AgentMessage],
    images: list[ImageContent] | None = None,
) -> AgentMessage
```

Send a prompt and return the complete assistant message.

**Parameters**:
- `input_data`: String, single message, or list of messages
- `images`: Optional list of image content blocks

**Returns**: The final `AssistantMessage`

**Raises**:
- `RuntimeError`: If agent is already streaming or no model configured

**Example**:
```python
response = await agent.prompt("Explain quantum computing")
print(response["content"][0]["text"])
```

#### prompt_text
```python
async def prompt_text(
    self,
    input_data: str | AgentMessage | list[AgentMessage],
    images: list[ImageContent] | None = None,
) -> str
```

Convenience method that returns just the text content.

#### continue_
```python
async def continue_(self) -> AgentMessage
```

Continue from current context without adding a new message. Used for retries after errors.

**Raises**:
- `RuntimeError`: If last message is from assistant (nothing to respond to)

### Streaming Methods

#### stream
```python
def stream(
    self,
    input_data: str | AgentMessage | list[AgentMessage],
    images: list[ImageContent] | None = None,
) -> AsyncIterator[AgentEvent]
```

Stream all agent events for a prompt.

**Yields**: `AgentEvent` objects (message_start, message_update, tool_execution_start, etc.)

**Example**:
```python
async for event in agent.stream("Tell me a story"):
    if event.type == "message_update":
        print(".", end="", flush=True)
    elif event.type == "tool_execution_start":
        print(f"\nUsing tool: {event.tool_name}")
```

#### stream_text
```python
def stream_text(
    self,
    input_data: str | AgentMessage | list[AgentMessage],
    images: list[ImageContent] | None = None,
) -> AsyncIterator[str]
```

Stream just the text deltas. Useful for simple streaming UIs.

**Example**:
```python
async for delta in agent.stream_text("Write a poem"):
    print(delta, end="", flush=True)
```

### Message Queue Methods

#### steer
```python
def steer(self, message: AgentMessage) -> None
```

Queue a steering message to interrupt the current agent run. The message is injected at the next opportunity (after current tool execution or turn).

**Use Case**: User types a new message while the agent is still processing.

#### follow_up
```python
def follow_up(self, message: AgentMessage) -> None
```

Queue a message to be processed after the current agent run completes.

**Use Case**: Automatic follow-up questions or chained prompts.

#### clear_steering_queue
```python
def clear_steering_queue(self) -> None
```
Remove all pending steering messages.

#### clear_follow_up_queue
```python
def clear_follow_up_queue(self) -> None
```
Remove all pending follow-up messages.

### Event Subscription

#### subscribe
```python
def subscribe(self, fn: Callable[[AgentEvent], None]) -> Callable[[], None]
```

Subscribe to all agent events. Returns an unsubscribe function.

**Example**:
```python
def log_event(event):
    logger.info(f"Agent event: {event.type}")

unsubscribe = agent.subscribe(log_event)
# ... later
unsubscribe()
```

### State Management

#### replace_messages
```python
def replace_messages(self, messages: list[AgentMessage]) -> None
```
Replace the entire message history.

#### append_message
```python
def append_message(self, message: AgentMessage) -> None
```
Append a single message to history.

#### clear_messages
```python
def clear_messages(self) -> None
```
Clear all messages (keeps system prompt and tools).

#### reset
```python
def reset(self) -> None
```
Reset agent to initial state (clears messages, queues, errors).

### Control Methods

#### abort
```python
def abort(self) -> None
```
Signal the current run to abort. The agent will stop at the next cancellation point.

#### wait_for_idle
```python
async def wait_for_idle(self) -> None
```
Wait for the current prompt/stream to complete.

### Properties

#### state
```python
@property
def state(self) -> AgentState
```
Current agent state (read-only reference).

#### session_id
```python
@property
def session_id(self) -> str | None
```
Session ID used for provider caching.

## AgentOptions

```python
@dataclass
class AgentOptions:
    initial_state: AgentState | None = None
    convert_to_llm: ConvertToLlmCallback | None = None
    transform_context: TransformContextCallback | None = None
    steering_mode: str = "one-at-a-time"  # "all" or "one-at-a-time"
    follow_up_mode: str = "one-at-a-time"  # "all" or "one-at-a-time"
    stream_fn: StreamFn | None = None
    session_id: str | None = None
    get_api_key: ApiKeyResolverCallback | None = None
    thinking_budgets: ThinkingBudgets | None = None
```

**Options**:

- `stream_fn`: Required. The streaming function (e.g., `stream_openrouter`)
- `convert_to_llm`: Callback to filter messages before LLM calls
- `transform_context`: Async callback to modify context before LLM calls
- `steering_mode`: "one-at-a-time" (default) or "all" - how to process steering queue
- `follow_up_mode`: "one-at-a-time" (default) or "all" - how to process follow-up queue
- `get_api_key`: Callback to resolve API keys dynamically

## Helper Functions

### extract_text
```python
def extract_text(message: AgentMessage | None) -> str
```
Extract concatenated text from an assistant message.

**Example**:
```python
response = await agent.prompt("Hello")
print(extract_text(response))  # "Hello! How can I help?"
```

### default_convert_to_llm
```python
async def default_convert_to_llm(messages: list[AgentMessage]) -> list[Message]
```
Default implementation that keeps only LLM-compatible message roles (user, assistant, tool_result).
