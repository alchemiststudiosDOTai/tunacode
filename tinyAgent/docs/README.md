# TinyAgent

A small, modular agent framework for building LLM-powered applications in Python.

## Overview

TinyAgent provides a lightweight foundation for creating conversational AI agents with tool use capabilities. It features:

- **Streaming-first architecture**: All LLM interactions support streaming responses
- **Tool execution**: Define and execute tools with structured outputs
- **Event-driven**: Subscribe to agent events for real-time UI updates
- **Provider agnostic**: Works with OpenRouter, proxy servers, or custom providers
- **Type-safe**: Full type hints throughout

## Quick Start

```python
import asyncio
from tinyagent import Agent, AgentOptions, OpenRouterModel, stream_openrouter

# Create an agent
agent = Agent(
    AgentOptions(
        stream_fn=stream_openrouter,
        session_id="my-session"
    )
)

# Configure
agent.set_system_prompt("You are a helpful assistant.")
agent.set_model(OpenRouterModel(id="anthropic/claude-3.5-sonnet"))

# Simple prompt
async def main():
    response = await agent.prompt_text("What is the capital of France?")
    print(response)

asyncio.run(main())
```

## Installation

```bash
pip install tinyagent
```

## Core Concepts

### Agent

The [`Agent`](api/agent.md) class is the main entry point. It manages:

- Conversation state (messages, tools, system prompt)
- Streaming responses
- Tool execution
- Event subscription

### Messages

Messages follow a typed dictionary structure:

- `UserMessage`: Input from the user
- `AssistantMessage`: Response from the LLM
- `ToolResultMessage`: Result from tool execution

### Tools

Tools are functions the LLM can call:

```python
from tinyagent import AgentTool, AgentToolResult

async def calculate_sum(tool_call_id: str, args: dict, signal, on_update) -> AgentToolResult:
    result = args["a"] + args["b"]
    return AgentToolResult(
        content=[{"type": "text", "text": str(result)}]
    )

tool = AgentTool(
    name="sum",
    description="Add two numbers",
    parameters={
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"}
        },
        "required": ["a", "b"]
    },
    execute=calculate_sum
)

agent.set_tools([tool])
```

### Events

The agent emits events during execution:

- `AgentStartEvent` / `AgentEndEvent`: Agent run lifecycle
- `TurnStartEvent` / `TurnEndEvent`: Single turn lifecycle
- `MessageStartEvent` / `MessageUpdateEvent` / `MessageEndEvent`: Message streaming
- `ToolExecutionStartEvent` / `ToolExecutionUpdateEvent` / `ToolExecutionEndEvent`: Tool execution

Subscribe to events:

```python
def on_event(event):
    print(f"Event: {event.type}")

unsubscribe = agent.subscribe(on_event)
```

## Rust Binding: `alchemy_llm_py`

TinyAgent ships with an optional Rust-based LLM provider located in
`bindings/alchemy_llm_py/`. It wraps the [`alchemy-llm`](https://crates.io/crates/alchemy-llm)
Rust crate and exposes it to Python via [PyO3](https://pyo3.rs), giving you native-speed
OpenAI-compatible streaming without leaving the Python process.

### Why

The pure-Python providers (`openrouter_provider.py`, `proxy.py`) work fine, but the Rust
binding gives you:

- **Lower per-token overhead** -- SSE parsing, JSON deserialization, and event dispatch all
  happen in compiled Rust with a multi-threaded Tokio runtime.
- **Unified provider abstraction** -- `alchemy-llm` normalizes differences across providers
  (OpenRouter, Anthropic, custom endpoints) behind a single streaming interface.
- **Full event fidelity** -- text deltas, thinking deltas, tool call deltas, and terminal
  events are all surfaced as typed Python dicts.

### How it works

```
Python (async)             Rust (Tokio)
─────────────────          ─────────────────────────
stream_alchemy_*()  ──>    alchemy_llm::stream()
                            │
AlchemyStreamResponse       ├─ SSE parse + deserialize
  .__anext__()       <──    ├─ event_to_py_value()
  (asyncio.to_thread)       └─ mpsc channel -> Python
```

1. Python calls `openai_completions_stream(model, context, options)` which is a `#[pyfunction]`.
2. The Rust side builds an `alchemy-llm` request, opens an SSE stream on a shared Tokio
   runtime, and sends events through an `mpsc` channel.
3. Python reads events by calling the blocking `next_event()` method via
   `asyncio.to_thread`, making it async-compatible without busy-waiting.
4. A terminal `done` or `error` event signals the end of the stream. The final
   `AssistantMessage` dict is available via `result()`.

### Building

Requires a Rust toolchain (1.70+) and [maturin](https://www.maturin.rs/).

```bash
pip install maturin
cd bindings/alchemy_llm_py
maturin develop          # debug build, installs into current venv
maturin develop --release  # optimized build
```

### Python API

Two functions are exposed from the `alchemy_llm_py` module:

| Function | Description |
|---|---|
| `collect_openai_completions(model, context, options?)` | Blocking. Consumes the entire stream and returns `{"events": [...], "final_message": {...}}`. Useful for one-shot calls. |
| `openai_completions_stream(model, context, options?)` | Returns an `OpenAICompletionsStream` handle for incremental consumption. |

The `OpenAICompletionsStream` handle has two methods:

| Method | Description |
|---|---|
| `next_event()` | Blocking. Returns the next event dict, or `None` when the stream ends. |
| `result()` | Blocking. Returns the final assistant message dict. |

All three arguments are plain Python dicts:

```python
model = {
    "id": "anthropic/claude-3.5-sonnet",
    "base_url": "https://openrouter.ai/api/v1/chat/completions",
    "provider": "openrouter",        # optional
    "headers": {"X-Custom": "val"},  # optional
    "reasoning": False,              # optional
    "context_window": 128000,        # optional
    "max_tokens": 4096,              # optional
}

context = {
    "system_prompt": "You are helpful.",
    "messages": [
        {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
    ],
    "tools": [                       # optional
        {"name": "sum", "description": "Add numbers", "parameters": {...}}
    ],
}

options = {
    "api_key": "sk-...",             # optional
    "temperature": 0.7,             # optional
    "max_tokens": 1024,             # optional
}
```

### Using via TinyAgent (high-level)

You don't need to call the Rust binding directly. Use the `alchemy_provider` module:

```python
from tinyagent import Agent, AgentOptions
from tinyagent.alchemy_provider import OpenAICompatModel, stream_alchemy_openai_completions

agent = Agent(
    AgentOptions(
        stream_fn=stream_alchemy_openai_completions,
        session_id="my-session",
    )
)
agent.set_model(
    OpenAICompatModel(
        id="anthropic/claude-3.5-sonnet",
        base_url="https://openrouter.ai/api/v1/chat/completions",
    )
)
```

### Limitations

- Only OpenAI-compatible `/chat/completions` streaming is supported.
- Image blocks are not yet supported (text and thinking blocks work).
- `next_event()` is blocking and runs in a thread via `asyncio.to_thread` -- this adds
  slight overhead compared to a native async generator, but keeps the GIL released during
  the Rust work.

## Documentation

- [Architecture](ARCHITECTURE.md): System design and component interactions
- [API Reference](api/): Detailed module documentation

## Project Structure

```
tinyagent/
├── agent.py              # Agent class
├── agent_loop.py         # Core agent execution loop
├── agent_tool_execution.py  # Tool execution helpers
├── agent_types.py        # Type definitions
├── openrouter_provider.py   # OpenRouter integration
├── alchemy_provider.py   # Rust-based provider
├── proxy.py              # Proxy server integration
└── proxy_event_handlers.py  # Proxy event parsing
```
