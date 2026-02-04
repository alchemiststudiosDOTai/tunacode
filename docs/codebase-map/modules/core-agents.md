---
title: Core Agent Orchestration
path: src/tunacode/core/agents
type: directory
depth: 1
description: AI agent creation, execution, and delegation system
exports: [process_request, RequestOrchestrator, AgentConfig, get_or_create_agent, HistoryPreparer]
seams: [M, D]
---

# Core Agent Orchestration

## Purpose

Manages AI agent lifecycle using pydantic-ai framework, including agent creation, request processing, tool execution, and multi-agent delegation.

## Provider Architecture

At `agent_config.py`, the `_create_model_with_retry()` function creates providers:

| Model Type | Provider Class |
|------------|----------------|
| Anthropic models | `AnthropicProvider` |
| All other models | `OpenAIProvider` |

OpenAI-compatible providers attach `validate_openai_chat_completion_response` as an HTTP response hook to detect error payloads and missing required fields before pydantic-ai validation.

The same HTTP client, retry logic, and provider instances are used for all requests.

## Message Flow

```
User Message
     |
     v
process_request() [main.py]
     |
     v
RequestOrchestrator created [main.py]
     |
     v
get_or_create_agent() [agent_config.py]
     |   - Always uses full tool set
     |   - Applies max_tokens (if set)
     v
prune_old_tool_outputs() [main.py]
     |   - Backward scan messages
     |   - Protect recent outputs
     |   - Replace old with placeholder
     v
agent.iter() -> Provider HTTP Request
```

## Key Components

### Main Entry Point

**process_request()** in `main.py`
- Creates RequestOrchestrator with agent configuration
- **Prunes old tool outputs before iteration**
- Iterates through agent responses until completion
- Handles tool execution and result aggregation
- Tracks iteration counters during the run
- Emits lifecycle debug logs when `SessionState.debug_mode` is enabled

### Agent Components

#### agent_config.py

- **get_or_create_agent()** - Factory for cached Agent instances
- **_create_model_with_retry()** - Model initialization with fallback
- **load_system_prompt()** - Loads system prompt
- **load_tunacode_context()** - Loads guide file into system prompt (defaults to `AGENTS.md`)

#### openai_response_validation.py

- **validate_openai_chat_completion_response()** - HTTP response hook that detects error payloads and missing required fields before pydantic-ai validation.

#### node_processor.py
- **_process_node()** - Core response processing loop
- Extracts tool calls from structured and text responses
- Handles empty/truncated response edge cases
- Detects submit tool calls for completion

#### streaming.py
- **stream_model_request_node()** - Streams token deltas with debug instrumentation
- Short-circuits when `debug_mode` is False to minimize overhead
- Capped debug accumulators prevent memory growth:
  - `DEBUG_STREAM_EVENT_HISTORY_LIMIT` (200) - max stored events
  - `DEBUG_STREAM_RAW_STREAM_MAX_CHARS` (20,000) - max raw stream size
  - `DEBUG_STREAM_EVENT_LOG_LIMIT` (5) - events logged per stream

#### streaming_debug.py
- Debug helper functions for stream previews, event summaries, and raw stream capture
- Owns `DEBUG_STREAM_*` constants and truncation limits for debug instrumentation

#### tool_executor.py
- **execute_tools_parallel()** - Concurrent read-only tool execution
- Implements exponential backoff retry logic
- Batches tools for efficiency
- Emits lifecycle debug logs for tool execution phases when debug mode is enabled

#### tool_buffer.py
- **ToolBuffer** - Collects and batches read-only tool calls
- Separates read-only from write operations

### Delegation System

#### delegation_tools.py
- **create_research_codebase_tool()** - Creates research delegation tool
- Spawns specialized research_agent for codebase exploration
- Research agent uses read-only tools only

#### research_agent.py
- Specialized agent with focused system prompt
- Limited tool set (glob, grep, read_file, list_dir)
- Returns structured research summaries

### State Management

#### state_transition.py
- **AgentStateMachine** - Tracks processing states
- Valid transitions: USER_INPUT → ASSISTANT → TOOL_EXECUTION → RESPONSE
- Ensures proper state flow

#### history_preparer.py
- **HistoryPreparer** - Prepares and sanitizes message history for agent runs
- Handles pruning, cleanup, and sanitization of conversation history

#### request_logger.py
- Logging utilities for request processing
- Functions: `log_history_state()`, `log_sanitized_history_state()`, `log_node_details()`

## Configuration

**AgentConfig** dataclass:
- **max_iterations** (default: 15) - Configured per-request iteration limit value

## Tool Categories

### Tool set

Full tool set with detailed descriptions:

| Category | Tools |
|----------|-------|
| Read-Only | glob, grep, list_dir, read_file, web_fetch |
| Write/Execute | bash, write_file, update_file |
| Completion | submit |
| Todo | todowrite, todoread, todoclear |
| Delegation | research_codebase |

## Message Types

Messages use pydantic-ai's standard types from `types/pydantic_ai.py`:

| Type | Purpose |
|------|---------|
| `ModelRequest` | Requests sent to model |
| `ModelResponse` | Responses from model |
| `ToolReturnPart` | Tool execution results |
| `SystemPromptPart` | System messages |
| `UserPromptPart` | User messages |
| `ToolCallPart` | Tool call requests |

**Message format is identical in both modes.** The only differences are:
- Content size (pruned more aggressively in local mode)
- System prompt content (shorter in local mode)
- Tool schemas (fewer in local mode)

Message history persistence happens after a run finishes or aborts.
`RequestOrchestrator` syncs `SessionState.conversation.messages` from
`agent_run.all_messages()` on normal completion, but **does not persist** on abort/cancel to prevent dangling tool calls.

When aborting (e.g., ESC pressed during tool execution):
- `agent_run` state is **not persisted** to avoid copying incomplete tool states
- Only cleanups already in `session.conversation.messages` are applied (dangling tool calls, empty responses, consecutive requests)
- This prevents 'Cannot provide a new user prompt when the message history contains unprocessed tool calls' errors

See `main.py:328-348` for the abort handling logic. The `message_has_tool_calls()` helper is now in `request_logger.py`.

## Integration Points

| Component | File | Integration |
|-----------|------|-------------|
| State | `core/state.py` | Session state, message history |
| Limits | `utils/limits.py` | `get_max_tokens()` |
| Compaction | `core/compaction.py` | `prune_old_tool_outputs()` |
| Prompting | `core/prompting/` | System prompt composition |
| Tools | `tools/` | Tool function registry |
| Types | `types/` | AgentRun, ModelName, MessageHistory |

## Seams (M, D)

**Modification Points:**
- Add new agent types (e.g., code_review_agent)
- Customize iteration settings and ReAct snapshot cadence
- Extend tool categorization logic
- Add new delegation patterns

**Extension Points:**
- Implement custom agent factories
- Add specialized tool executors
- Create new state machine transitions
