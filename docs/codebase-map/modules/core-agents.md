---
title: Core Agent Orchestration
path: src/tunacode/core/agents
type: directory
depth: 1
description: AI agent creation, execution, and delegation system
exports: [process_request, RequestOrchestrator, AgentConfig, get_or_create_agent]
seams: [M, D]
---

# Core Agent Orchestration

## Purpose

Manages AI agent lifecycle using pydantic-ai framework, including agent creation, request processing, tool execution, and multi-agent delegation.

## Provider Architecture

**Both local and API modes use identical providers.** There are no separate LocalProvider implementations.

At `agent_config.py:308-359`, the `_create_model_with_retry()` function creates providers:

| Model Type | Provider Class |
|------------|----------------|
| Anthropic models | `AnthropicProvider` |
| All other models | `OpenAIProvider` |

The same HTTP client, retry logic, and provider instances are used regardless of mode. All optimization happens at the **message preparation layer** before any provider interaction.

## Message Flow

```
User Message
     |
     v
process_request() [main.py:527]
     |
     v
RequestOrchestrator created [main.py:536-544]
     |
     v
get_or_create_agent() [agent_config.py]
     |   - Selects template (LOCAL_TEMPLATE vs MAIN_TEMPLATE)
     |   - Selects tools (6 vs 11)
     |   - Applies max_tokens
     v
prune_old_tool_outputs() [main.py:369]
     |   - Backward scan messages
     |   - Protect recent outputs
     |   - Replace old with placeholder
     v
agent.iter() -> Provider HTTP Request
     |
     v
(Same pydantic-ai message format for both modes)
```

## Key Components

### Main Entry Point

**process_request()** in `main.py`
- Creates RequestOrchestrator with agent configuration
- **Prunes old tool outputs before iteration** (line 369)
- Iterates through agent responses until completion
- Handles tool execution and result aggregation
- Tracks iteration counters during the run
- Emits lifecycle debug logs when `SessionState.debug_mode` is enabled

### Agent Components

#### agent_config.py

- **get_or_create_agent()** - Factory for cached Agent instances
- **_create_model_with_retry()** - Model initialization with fallback
- **load_system_prompt()** - Selects template based on mode (lines 236-245):
  - Standard mode: `MAIN_TEMPLATE` (11 sections, ~3,500 tokens)
  - Local mode: `LOCAL_TEMPLATE` (3 sections, ~1,100 tokens)
- **load_tunacode_context()** - Loads guide file into system prompt:
  - Standard mode: loads `AGENTS.md` (or `settings.guide_file`)
  - Local mode: loads `local_prompt.md` for minimal tokens

#### node_processor.py
- **_process_node()** - Core response processing loop
- Extracts tool calls from structured and text responses
- Handles empty/truncated response edge cases
- Detects submit tool calls for completion

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

#### iteration_manager.py (in main.py)
- **IterationManager** - Tracks iteration counters in session state

### ReAct Pattern Support

#### ReactSnapshotManager
- Captures agent thought process snapshots
- Injects structured guidance into context
- Nudges agent toward next logical step

## Configuration

**AgentConfig** dataclass:
- **max_iterations** (default: 15) - Configured per-request iteration limit value
- **forced_react_interval** (default: 2) - Iteration interval for forced ReAct snapshots
- **forced_react_limit** (default: 5) - Max forced ReAct snapshots per request

## Tool Categories

### Standard Mode (11 tools)

Full tool set with detailed descriptions:

| Category | Tools |
|----------|-------|
| Read-Only | glob, grep, list_dir, read_file, react, web_fetch |
| Write/Execute | bash, write_file, update_file |
| Completion | submit |
| Todo | todowrite, todoread, todoclear |
| Delegation | research_codebase |

### Local Mode (6 tools)

Minimal tool set for small context windows (8k-16k tokens):

| Tool | Description | Standard Description |
|------|-------------|---------------------|
| bash | "Shell" | Full multi-paragraph description |
| read_file | "Read" | Full multi-paragraph description |
| update_file | "Edit" | Full multi-paragraph description |
| write_file | "Write" | Full multi-paragraph description |
| glob | "Find" | Full multi-paragraph description |
| list_dir | "List" | Full multi-paragraph description |
| react | "React" | Full multi-paragraph description |
| submit | "Submit" | Full multi-paragraph description |

**Excluded in local mode:** grep, web_fetch, todo tools, research_codebase

Tool selection at `agent_config.py:406-444`.

### Token Budget Comparison

| Component | Standard Mode | Local Mode |
|-----------|--------------|------------|
| System prompt | ~3,500 tokens | ~1,100 tokens |
| Guide file | ~2,000+ tokens | ~500 tokens |
| Tool schemas | ~1,800 tokens | ~575 tokens |
| **Total base** | **~7,300+** | **~2,200** |

With 10k context window:
- Standard mode: ~2,700 tokens for conversation
- Local mode: ~7,800 tokens for conversation

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

See `main.py:577-601` for the abort handling logic and `main.py:626-653` for the improved `_message_has_tool_calls` helper.

## Integration Points

| Component | File | Integration |
|-----------|------|-------------|
| State | `core/state.py` | Session state, message history |
| Limits | `core/limits.py` | `is_local_mode()`, `get_max_tokens()` |
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
