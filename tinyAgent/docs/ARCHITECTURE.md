# Architecture

This document describes the architecture of TinyAgent: where components live, what they do, and how they interact.

## Design Principles

1. **Streaming-first**: All LLM interactions support streaming; non-streaming is a special case
2. **Event-driven**: Components communicate through events for loose coupling
3. **Type safety**: Full type hints; runtime uses TypedDict for flexibility
4. **Boundary preservation**: AgentMessage (internal) vs Message (LLM-boundary) separation

## Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Agent                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   State     │  │  Listeners  │  │   Message Queues    │  │
│  │  (AgentState)│  │   (set)     │  │  (steering/follow-up)│ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      Agent Loop                             │
│         (agent_loop / agent_loop_continue)                  │
└─────────────────────────────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Stream    │     │   Execute   │     │   Transform     │
│   Function  │     │   Tools     │     │   Context       │
│(StreamFn)   │     │             │     │                 │
└─────────────┘     └─────────────┘     └─────────────────┘
```

## Module Responsibilities

### agent_types.py

**What**: Type definitions using TypedDict and dataclasses.

**Key Types**:
- `AgentMessage`: Internal message format (union of Message + custom types)
- `Message`: LLM-compatible messages (user/assistant/tool_result)
- `AgentEvent`: All event types emitted during agent execution
- `AgentState`: Complete agent state snapshot
- `AgentTool`: Tool definition with execute function
- `StreamFn`: Protocol for LLM streaming implementations

**Design Decision**: TypedDict allows optional fields with runtime flexibility while maintaining type safety.

### agent_loop.py

**What**: Core agent execution loop. Single responsibility: orchestrate LLM calls and tool execution.

**Key Functions**:
- `agent_loop()`: Start new agent run with prompt messages
- `agent_loop_continue()`: Continue from existing context (for retries)
- `stream_assistant_response()`: Stream a single assistant message
- `run_loop()`: Main loop logic shared by both entry points

**Flow**:
1. Emit `AgentStartEvent`
2. Outer loop: Check for follow-up messages after agent would stop
3. Inner loop: Process turns (LLM call → tool execution → steering)
4. Emit `AgentEndEvent`

**Steering**: User can inject messages mid-run via `steer()`. The loop checks for steering messages after each tool execution.

### agent_tool_execution.py

**What**: Tool execution logic. Extracts tool calls from assistant messages and executes them.

**Key Functions**:
- `execute_tool_calls()`: Execute all tool calls in a message
- `skip_tool_call()`: Mark a tool call as skipped (due to steering interruption)
- `validate_tool_arguments()`: Validate args against tool schema (placeholder)

**Execution Flow**:
1. Extract tool calls from assistant message content
2. For each tool call:
   - Find matching tool by name
   - Emit `ToolExecutionStartEvent`
   - Execute tool (async)
   - Emit `ToolExecutionEndEvent`
   - Check for steering messages (interrupt remaining tools)
3. Return tool results as `ToolResultMessage` objects

### agent.py

**What**: High-level Agent class that wraps the agent loop with state management.

**Responsibilities**:
- Maintain `AgentState` (messages, tools, model, etc.)
- Manage event listeners
- Handle steering/follow-up message queues
- Provide sync-like interface (`prompt()`, `stream()`)
- Convert internal events to state updates

**Key Methods**:
- `prompt()`: Send message, wait for complete response
- `stream()`: Stream all agent events
- `stream_text()`: Stream just text deltas
- `steer()`: Queue a steering message (interrupts current run)
- `follow_up()`: Queue a message for after current run

**Event Handling**: Internal handlers update state on events:
- `message_start/update`: Update `stream_message` in state
- `message_end`: Append message to history
- `tool_execution_start/end`: Track pending tool calls
- `turn_end`: Capture errors from assistant messages
- `agent_end`: Mark streaming as complete

### Providers (openrouter_provider.py, alchemy_provider.py)

**What**: Implement `StreamFn` protocol for specific LLM backends.

**OpenRouter Provider**:
- HTTP streaming via httpx
- OpenAI-compatible message format
- SSE parsing for streaming responses
- Tool call extraction from deltas

**Alchemy Provider**:
- Rust-based implementation via PyO3
- Blocking calls in thread pool
- Lower overhead for high-throughput scenarios

### Proxy (proxy.py, proxy_event_handlers.py)

**What**: Client for apps that route LLM calls through a proxy server.

**Use Case**: Web apps where the server manages API keys and provider selection.

**Components**:
- `ProxyStreamResponse`: Implements `StreamResponse` for proxy SSE streams
- `process_proxy_event()`: Parse proxy-specific events into standard events

## Message Type Boundaries

```
┌─────────────────┐     convert_to_llm()     ┌─────────────────┐
│  AgentMessage   │ ───────────────────────► │     Message     │
│   (internal)    │                          │  (LLM boundary) │
│                 │ ◄─────────────────────── │                 │
│ - UserMessage   │     tool results         │ - user          │
│ - AssistantMsg  │                          │ - assistant     │
│ - ToolResult    │                          │ - tool_result   │
│ - Custom types  │                          │                 │
└─────────────────┘                          └─────────────────┘
```

The `convert_to_llm` callback filters custom message types before sending to LLM. This allows agents to maintain internal state (annotations, metadata) that isn't sent to the model.

Default implementation (`default_convert_to_llm`): Keep only `user`, `assistant`, and `tool_result` roles.

## Event System

Events flow upward through the system:

```
┌─────────────────────────────────────────────────────────┐
│  Provider (OpenRouter/Alchemy/Proxy)                    │
│  Emits: AssistantMessageEvent (text_delta, tool_call_*) │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Agent Loop                                             │
│  Translates: AssistantMessageEvent → AgentEvent         │
│  Emits: message_start, message_update, message_end      │
│         tool_execution_start, tool_execution_end        │
│         turn_start, turn_end, agent_start, agent_end    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Agent Class                                            │
│  Updates state based on events                          │
│  Forwards events to subscribers                         │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Application                                            │
│  Receives events, updates UI                            │
└─────────────────────────────────────────────────────────┘
```

## State Management

`AgentState` is a single source of truth:

```python
AgentState = {
    "system_prompt": str,
    "model": Model | None,
    "thinking_level": ThinkingLevel,
    "tools": list[AgentTool],
    "messages": list[AgentMessage],
    "is_streaming": bool,
    "stream_message": AgentMessage | None,  # Currently streaming
    "pending_tool_calls": set[str],
    "error": str | None,
}
```

State is mutated only by internal event handlers in the Agent class, keeping side effects centralized.

## Concurrency Model

- Agent runs in an asyncio task
- `agent_loop()` creates the task and returns immediately with an `EventStream`
- Application iterates the stream or awaits `result()`
- Steering uses thread-safe queues; agent checks queue at well-defined points
- Abort via `asyncio.Event` checked during streaming

## Extension Points

1. **Custom StreamFn**: Implement `StreamResponse` protocol for new providers
2. **convert_to_llm**: Filter/transform messages before LLM calls
3. **transform_context**: Modify context (e.g., add retrieval-augmented generation)
4. **get_api_key**: Dynamic API key resolution
5. **Custom AgentEvent**: Extend event types for domain-specific needs
