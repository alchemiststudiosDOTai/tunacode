# Agent Loop Module

Core agent execution loop. Orchestrates LLM calls and tool execution.

## Main Entry Points

### agent_loop
```python
def agent_loop(
    prompts: list[AgentMessage],
    context: AgentContext,
    config: AgentLoopConfig,
    signal: asyncio.Event | None = None,
    stream_fn: StreamFn | None = None,
) -> EventStream
```

Start an agent loop with one or more new prompt messages.

**Parameters**:
- `prompts`: Initial messages to process
- `context`: Current agent context (system prompt, message history, tools)
- `config`: Loop configuration (model, callbacks)
- `signal`: Optional abort signal
- `stream_fn`: Optional override for the stream function

**Returns**: `EventStream` that yields events and can produce final result

**Events Emitted**:
- `agent_start`, `turn_start`
- `message_start`, `message_end` (for each prompt)
- `message_start`, `message_update`, `message_end` (for assistant response)
- `tool_execution_start`, `tool_execution_end` (for each tool)
- `turn_end`, `agent_end`

**Example**:
```python
stream = agent_loop(
    prompts=[{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
    context=AgentContext(system_prompt="You are helpful", messages=[], tools=[]),
    config=AgentLoopConfig(model=model, convert_to_llm=default_convert_to_llm),
)

async for event in stream:
    print(event.type)

messages = await stream.result()
```

### agent_loop_continue
```python
def agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: asyncio.Event | None = None,
    stream_fn: StreamFn | None = None,
) -> EventStream
```

Continue an agent loop from the current context without adding new messages.

**Use Case**: Retries after errors or context overflow. The context already has a user message or tool results that need a response.

**Requirement**: The last message in context must have role != "assistant".

**Raises**: `ValueError` if no messages or last message is from assistant

## Streaming Helper

### stream_assistant_response
```python
async def stream_assistant_response(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: asyncio.Event | None,
    stream: EventStream,
    stream_fn: StreamFn | None = None,
) -> AssistantMessage
```

Stream a single assistant response from the LLM.

**Flow**:
1. Build LLM context (apply transform_context, convert_to_llm)
2. Resolve API key
3. Call stream_fn to get StreamResponse
4. Stream events, updating partial message
5. Return final message

**Events Emitted**:
- `message_start` (if not already emitted)
- `message_update` (for each content delta)
- `message_end`

### stream_simple
```python
async def stream_simple(
    model: Model,
    context: Context,
    options: SimpleStreamOptions,
) -> StreamResponse
```

Placeholder stream function that raises `NotImplementedError`.

Real implementations must be passed via `AgentOptions.stream_fn` or `AgentLoopConfig`.

## Event Stream Factory

### create_agent_stream
```python
def create_agent_stream() -> EventStream
```

Create a standard event stream for agent events.

The stream considers `agent_end` as the end event and extracts messages from it.

## Internal Types

### ResponseStreamState
```python
@dataclass
class ResponseStreamState:
    partial_message: AssistantMessage | None = None
    added_partial: bool = False
```

Tracks streaming state within a single assistant response.

### TurnProcessingResult
```python
@dataclass
class TurnProcessingResult:
    pending_messages: list[AgentMessage]
    has_more_tool_calls: bool
    first_turn: bool
    should_continue: bool
```

Result from processing a single turn.

## Loop Execution Flow

```
agent_loop()
    └── run_loop()
            │
            ├── Outer loop: Check follow-up messages
            │   └── Break if none
            │
            └── Inner loop: Process turns
                    │
                    ├── _process_turn()
                    │   ├── stream_assistant_response()
                    │   │   └── Provider streaming
                    │   ├── _extract_tool_calls()
                    │   └── execute_tool_calls()
                    │       └── For each tool: _execute_single_tool()
                    │
                    └── Check steering messages
```

## Steering and Follow-up

### Steering

Steering messages interrupt the current run:

1. User calls `agent.steer(message)`
2. Message added to steering queue
3. After current tool execution, loop checks `get_steering_messages()`
4. If steering messages exist, they become pending for next turn
5. Remaining tool calls are skipped

### Follow-up

Follow-up messages continue after the agent would stop:

1. User calls `agent.follow_up(message)`
2. Message added to follow-up queue
3. When inner loop ends (no more tool calls), check `get_follow_up_messages()`
4. If follow-up exists, set as pending and continue outer loop

### Modes

Both queues support two modes:

- `"one-at-a-time"` (default): Process one message per check
- `"all"`: Process all queued messages at once

## SSE Event Constants

```python
STREAM_UPDATE_EVENTS = {
    "text_start", "text_delta", "text_end",
    "thinking_start", "thinking_delta", "thinking_end",
    "tool_call_start", "tool_call_delta", "tool_call_end",
}
```

Events that update the partial message during streaming.
