---
title: Core Layer
summary: Agent loop orchestration, context compaction, session state management, structured logging, and the state machine.
read_when: Debugging agent behavior, modifying the request lifecycle, or changing how session state is persisted.
depends_on: [types, infrastructure, configuration, tools]
feeds_into: [ui]
---

# Core Layer

**Package:** `src/tunacode/core/`

## What

The engine. Takes a user message, routes it through a tinyagent `Agent`, handles streaming events, manages compaction, tracks tool calls, and persists session state.

## Sub-Packages

### agents/ -- Agent Loop

| File | Purpose |
|------|---------|
| `main.py` | `RequestOrchestrator` -- the main request lifecycle. `process_request()` is the public entry point. Handles: history coercion, pre-request compaction, streaming event dispatch, abort cleanup, empty-response intervention, context-overflow retry. |
| `agent_components/__init__.py` | Re-exports from sub-modules. |
| `agent_components/agent_config.py` | `get_or_create_agent()` -- builds or retrieves a cached tinyagent `Agent`. Configures: system prompt, tools, model, stream function, API key resolver, compaction transform. `invalidate_agent_cache()` clears both module and session caches after abort/timeout. |
| `agent_components/agent_helpers.py` | Human-readable tool descriptions for UI panels. `create_empty_response_message()` builds the intervention prompt when the model returns nothing. |
| `agent_components/state_transition.py` | `AgentStateMachine` -- thread-safe FSM with states: `USER_INPUT -> ASSISTANT -> TOOL_EXECUTION -> RESPONSE`. `AGENT_TRANSITION_RULES` defines valid edges. |
| `agent_components/openai_response_validation.py` | `validate_openai_chat_completion_response()` -- intercepts non-streaming HTTP responses from OpenAI-compatible providers, checks for error payloads and missing fields, raises `AgentError` with troubleshooting steps. |
| `resume/sanitize.py` | Cleans persisted session messages for safe resume (removes dangling tool calls, fixes structural violations). |
| `resume/sanitize_debug.py` | Debug instrumentation for sanitization. |

### compaction/ -- Context Window Management

| File | Purpose |
|------|---------|
| `controller.py` | `CompactionController` -- threshold check, force-compact, summary injection, compaction record management. `get_or_create_compaction_controller()` returns the session-scoped singleton. `apply_compaction_messages()` writes compacted history back to session. |
| `summarizer.py` | `ContextSummarizer` -- calculates retention boundaries, serializes messages to text, generates summaries via a pluggable `SummaryGenerator` callback. |
| `prompts.py` | Prompt templates for fresh and iterative summarization. |
| `types.py` | `CompactionOutcome` (status + reason + messages), `CompactionRecord` (summary + token counts + compaction history). Status/reason string constants. |

### session/ -- State Persistence

| File | Purpose |
|------|---------|
| `state.py` | `SessionState` dataclass -- the single container for all mutable state (config, agents, conversation, runtime, usage, compaction, recursion tracking). `StateManager` -- singleton that owns a `SessionState`, loads user config, and provides `save_session()` / `load_session()` / `list_sessions()`. |

### logging/ -- Structured Logging

| File | Purpose |
|------|---------|
| `manager.py` | `get_logger()` returns the singleton structured logger. Supports a TUI callback for rendering log entries in the chat. |
| `handlers.py` | Log handlers (file, TUI). |
| `levels.py` | Custom log levels (`lifecycle`, `debug`, `info`, `warning`, `error`). |
| `records.py` | Structured log record types. |

### types/ -- Core Protocols

| File | Purpose |
|------|---------|
| `__init__.py` | Re-exports everything below. |
| `state.py` | `SessionStateProtocol` and `StateManagerProtocol` -- structural typing contracts that break circular imports between session and agents. |
| `state_structures.py` | `ConversationState`, `TaskState`, `RuntimeState`, `UsageState` -- decomposed sub-states slotted into `SessionState`. |
| `agent_state.py` | `AgentState` enum (`USER_INPUT`, `ASSISTANT`, `TOOL_EXECUTION`, `RESPONSE`). `ResponseState` dataclass for completion tracking. |
| `tool_registry.py` | `ToolCallRegistry` -- ordered registry tracking each tool call through `PENDING -> RUNNING -> COMPLETED/FAILED/CANCELLED`. |

### Other

| File | Purpose |
|------|---------|
| `debug/usage_trace.py` | `log_usage_update()` -- structured logging of per-request usage metrics. |
| `ui_api/` | Bridge between core and UI. See [ui/ui.md](../ui/ui.md) for details. |

## How

### Request Lifecycle

```
User types message
    |
    v
TextualReplApp._process_request(message)
    |
    v
process_request(message, model, state_manager, callbacks...)
    |
    v
RequestOrchestrator.run()
    |-- _initialize_request()      reset counters, generate request_id
    |-- get_or_create_agent()      build/cache tinyagent Agent
    |-- _coerce_tinyagent_history() validate session messages are dicts
    |-- _compact_history_for_request() threshold check + summarize if needed
    |-- agent.replace_messages()    load compacted history into agent
    |-- _run_stream(agent, ...)     main event loop
    |       |
    |       |  async for event in agent.stream(message):
    |       |    message_update  -> streaming_callback (UI delta)
    |       |    message_end     -> parse usage, update session totals
    |       |    tool_execution_start -> register tool, notify UI
    |       |    tool_execution_end   -> mark complete/failed, notify UI
    |       |    turn_end        -> increment iteration, enforce max
    |       |    agent_end       -> persist messages to session
    |       |
    |-- _retry_after_context_overflow_if_needed()
    |       force-compact and retry once if API returns context_length_exceeded
    |
    v
Return to UI for rendering
```

### Compaction Flow

```
CompactionController.check_and_compact(messages, max_tokens)
    |-- should_compact?  estimate_tokens vs (max_tokens - reserve - keep_recent)
    |       no  -> return skip outcome
    |       yes -> ContextSummarizer
    |                  |-- calculate_retention_boundary (walk backward, find safe split)
    |                  |-- serialize_messages (to text transcript)
    |                  |-- _summary_generator (call LLM with summarize prompt)
    |                  |-- return summary string
    |-- update CompactionRecord on session
    |-- return CompactionOutcome(status=compacted, messages=retained)
```

### Session Persistence

`StateManager.save_session()` serializes to JSON:
- Messages (must be tinyagent dicts; non-dict = hard error)
- Compaction record
- Usage totals
- Model, project_id, timestamps

`StateManager.load_session()` deserializes and separates thought entries from message history.

## Why

The `RequestOrchestrator` class exists to keep the streaming event loop testable and the callback wiring explicit. Each event type has its own handler method -- no giant switch statement.

Compaction is request-scoped (one compaction per request at most) to avoid compacting the same history repeatedly when the model makes multiple turns.

The `StateManagerProtocol` breaks the circular dependency between session state and agent creation -- agents need state, state stores agents.
