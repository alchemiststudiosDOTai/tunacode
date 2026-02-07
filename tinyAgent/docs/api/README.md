# API Reference

Complete API documentation for the tinyagent package.

## Core Modules

| Module | Description |
|--------|-------------|
| [agent](agent.md) | `Agent` class - main entry point |
| [agent_types](agent_types.md) | Type definitions (messages, events, tools) |
| [agent_loop](agent_loop.md) | Core execution loop |
| [agent_tool_execution](agent_tool_execution.md) | Tool execution helpers |

## Providers

| Module | Description |
|--------|-------------|
| [providers](providers.md) | OpenRouter, Alchemy (Rust), and Proxy providers |

## Quick Reference

### Common Imports

```python
# Agent
from tinyagent import Agent, AgentOptions

# Types
from tinyagent import (
    AgentMessage,
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    AgentTool,
    AgentToolResult,
    AgentEvent,
    AgentState,
)

# Providers
from tinyagent import OpenRouterModel, stream_openrouter
from tinyagent.alchemy_provider import (
    OpenAICompatModel,
    stream_alchemy_openai_completions,
)

# Helpers
from tinyagent import (
    extract_text,
    default_convert_to_llm,
)
```

### Type Hierarchy

```
AgentMessage
├── Message (LLM-compatible)
│   ├── UserMessage
│   ├── AssistantMessage
│   └── ToolResultMessage
└── CustomAgentMessage (custom roles)

AgentEvent
├── AgentStartEvent / AgentEndEvent
├── TurnStartEvent / TurnEndEvent
├── MessageStartEvent / MessageUpdateEvent / MessageEndEvent
└── ToolExecutionStartEvent / ToolExecutionUpdateEvent / ToolExecutionEndEvent

Content Types
├── TextContent
├── ImageContent
├── ThinkingContent
└── ToolCallContent
```

### Callback Signatures

```python
from typing import Awaitable, Callable
from tinyagent import AgentMessage, Message, AgentToolResult

# Convert messages before LLM call
ConvertToLlmCallback = Callable[
    [list[AgentMessage]],
    Awaitable[list[Message]]
]

# Transform context before LLM call
TransformContextCallback = Callable[
    [list[AgentMessage], asyncio.Event | None],
    Awaitable[list[AgentMessage]]
]

# Resolve API key dynamically
ApiKeyResolverCallback = Callable[
    [str],  # provider name
    Awaitable[str | None]
]

# Tool progress updates
AgentToolUpdateCallback = Callable[[AgentToolResult], None]
```
