---
summary: |
  User message enters process_request() which spawns RequestOrchestrator.
  The orchestrator sanitizes history, runs agent.iter() in a loop yielding nodes,
  streams responses via callbacks, dispatches tools in parallel, and persists messages.

when_to_read:
  - Adding a new tool (understand dispatch_tools discovery)
  - Debugging stream issues (trace streaming.py flow)
  - Fixing history corruption (see resume/sanitize.py)
  - Understanding state bugs (three-level state architecture)
  - Modifying the loop (know four phases of RequestOrchestrator)

ontology:
  RequestOrchestrator:
    owns: request lifecycle, iteration loop
    depends: ResponseState, agent, sanitization
  ResponseState:
    owns: state machine, transitions
    depends: null
  tool_dispatcher:
    owns: tool discovery, fallback parsing
    depends: tool_executor
  tool_executor:
    owns: parallel execution, retry logic
    depends: tool implementations
  streaming:
    owns: token delivery, prefix seeding
    depends: pydantic-ai stream API
  resume/sanitize:
    owns: history cleanup
    depends: resume/prune
---

# Agent Loop and Orchestration

This document maps the main agent loop and orchestration architecture in tunacode.

## Overview

The agent loop is the core execution engine that processes user requests, coordinates tool execution, manages streaming responses, and maintains conversation state. It follows a structured pipeline pattern with clear separation of concerns.

## Entry Point

**File:** `src/tunacode/core/agents/main.py:369-389`
**Function:** `process_request()`

```python
async def process_request(
    message: str,
    model: ModelName,
    state_manager: StateManagerProtocol,
    tool_callback: ToolCallback | None = None,
    streaming_callback: StreamingCallback | None = None,
    tool_result_callback: ToolResultCallback | None = None,
    tool_start_callback: ToolStartCallback | None = None,
    notice_callback: NoticeCallback | None = None,
) -> AgentRun:
```

Called from the UI layer, this function creates a `RequestOrchestrator` instance that drives the entire request lifecycle.

## Core Loop Structure

**Class:** `RequestOrchestrator` (main.py:115-348)

The loop runs as an async context manager with four phases:

### Phase 1: Initialize Request

**Function:** `_initialize_request()` (lines 190-195)

- Sets up request ID
- Resets session state
- Records original query

### Phase 2: Prepare Message History

**Class:** `HistoryPreparer` (history_preparer.py)
**Function:** `HistoryPreparer.prepare()` (lines 31-62)

- Sanitizes and validates conversation history
- Prunes old tool outputs for token efficiency
- Cleans up dangling tool calls
- Drops trailing request if needed to avoid consecutive requests
- Returns baseline message count to track external additions

### Phase 3: Agent Iteration Loop

**Function:** `_run_agent_iterations()` (lines 231-268)

```python
async with agent.iter(self.message, message_history=message_history) as run_handle:
    iteration_index = 1
    async for node in run_handle:
        should_stop = await self._handle_iteration_node(...)
        if should_stop:
            break
        iteration_index += 1

    self._persist_run_messages(run_handle, baseline_message_count)
```

Each iteration yields a `node` from pydantic-ai's agent framework.

### Phase 4: Persist Messages

**Function:** `_persist_run_messages()`

Merges run messages with any external additions to the conversation history.

## Message Flow

| Step | File:Line | Function |
|------|-----------|----------|
| User message arrives | main.py:369 | `process_request()` |
| Passed to orchestrator | main.py:115 | `RequestOrchestrator` |
| History prepared | history_preparer.py:31 | `HistoryPreparer.prepare()` |
| Sent to model | main.py:245 | `agent.iter()` |
| Response nodes yielded | main.py:253 | `async for node in run_handle` |
| Node processed | main.py:270-326 | `_handle_iteration_node()` |

## Tool Execution

**File:** `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`
**Function:** `dispatch_tools()` (lines 235-368)

### Tool Discovery

1. Inspects response parts for `part_kind == "tool-call"` (line 263)
2. Extracts tool name, tool_call_id, and args from each part (lines 270-292)
3. Records tool calls in the runtime tool registry

### Fallback Parsing

If no structured tool calls found, attempts fallback parsing from text (lines 294-307) using `parse_tool_calls_from_text()` to extract tool calls from markdown/text format.

### Parallel Execution

**File:** `src/tunacode/core/agents/agent_components/tool_executor.py` (lines 54-141)

- Batches tools for parallel execution via `execute_tools_parallel()`
- Respects `TUNACODE_MAX_PARALLEL` env var (default: CPU count)
- Retry logic: Exponential backoff with jitter, up to `TOOL_MAX_RETRIES` attempts
- Non-retryable errors: `UserAbortError`, `ModelRetry`, `ValidationError`, etc.

### Result Handling

- Tool results consumed via `_emit_tool_returns()` in orchestrator
- Results sent to `tool_result_callback` for UI display
- Tool registry marked as completed

### State Transitions

- Before tools: `response_state.transition_to(AgentState.TOOL_EXECUTION)`
- After tools: `response_state.transition_to(AgentState.RESPONSE)`

## Streaming

**File:** `src/tunacode/core/agents/agent_components/streaming.py`
**Function:** `stream_model_request_node()` (lines 242-302)

### Streaming Trigger

Called from `_handle_iteration_node()` when:
- Node is a model request
- `streaming_callback` is provided

### Token-Level Streaming

```python
async with node.stream(agent_run_ctx) as request_stream:
    async for event in request_stream:
        # Process delta events
        streaming_callback(delta)
```

1. Opens async stream context
2. Consumes stream events via `_consume_request_stream()`
3. Each event processed by `_handle_part_delta_event()`
4. Text deltas extracted and sent to `streaming_callback()`

### Prefix Seeding

Captures pre-first-delta text to avoid partial token artifacts (lines 77-124). Computes overlap with first delta to avoid duplication.

### Debug Instrumentation

- Tracks stream state: `first_delta_seen`, `seeded_prefix_sent`, `debug_event_count`
- Accumulates raw stream text in `session._debug_raw_stream_accum`
- Records stream events in `session._debug_events`

## State Management

State is maintained across three levels:

### Session-Level Runtime State

**File:** `src/tunacode/core/types/state.py`

Holds:
- `conversation.messages`: All pydantic-ai message objects
- `runtime.current_iteration`: Current iteration number
- `runtime.iteration_count`: Total iterations executed
- `runtime.tool_registry`: Tool call registry tracking calls and results
- `runtime.batch_counter`: Tool batch counter
- `runtime.consecutive_empty_responses`: Empty response streak counter
- `runtime.request_id`: Current request ID

### Response State Machine

**File:** `src/tunacode/core/agents/agent_components/response_state.py`
**Class:** `ResponseState` (lines 12-130)

Thread-safe state machine tracking:
- `current_state`: One of `USER_INPUT | ASSISTANT | TOOL_EXECUTION | RESPONSE`
- `has_user_response`: Whether user-visible output generated
- `task_completed`: Whether agent signaled completion

### State Transitions

**File:** `src/tunacode/core/agents/agent_components/state_transition.py`
**Rules:** Lines 105-112

```
USER_INPUT     -> ASSISTANT
ASSISTANT      -> TOOL_EXECUTION or RESPONSE
TOOL_EXECUTION -> RESPONSE
RESPONSE       -> ASSISTANT (loop back for continued work)
```

### History Sanitization

**File:** `src/tunacode/core/agents/resume/sanitize.py`

Before each run:
- Remove consecutive requests (avoid double-requests)
- Remove dangling tool calls (calls without returns)
- Remove empty responses (no content or tools)
- Token pruning on old tool outputs (preserve context window)

## Key Orchestration Points

### _handle_iteration_node()

**File:** `main.py:270-326`

The main coordination hub. Orchestrates:
1. Logs iteration start (via `log_node_details()` from `request_logger.py`)
2. Calls `stream_model_request_node()` if streaming enabled
3. Calls `process_node()` to handle node response
4. Tracks empty responses via `EmptyResponseHandler`
5. Updates response state from node output
6. Checks for task completion
7. Returns `should_stop` to break loop

### process_node()

**File:** `orchestrator/orchestrator.py:179-297`

The response processor. Handles:
1. Updates response state to ASSISTANT
2. Emits tool returns from request part
3. Records agent thoughts
4. Updates usage metrics
5. Processes response parts
6. Dispatches tools
7. Detects empty/truncated responses

### dispatch_tools()

**File:** `tool_dispatcher.py:235-368`

Tool orchestration. Handles:
1. Extracts tool calls from parts
2. Applies fallback parsing if needed
3. Registers tools in runtime
4. Marks tools as running
5. Executes tools in parallel
6. Handles tool failures with retry logic

### EmptyResponseHandler

**File:** `main.py:73-112`

Tracks consecutive empty responses and prompts user intervention when threshold exceeded (>= 1 consecutive empty).

## Flow Diagram

```
process_request()
    |
    v
RequestOrchestrator.run()
    |
    +---> _initialize_request()
    |
    +---> _prepare_message_history()
    |         +-- sanitize + token prune
    |
    +---> agent.iter(message, history)
    |         |
    |         +---> async for node:
    |                   |
    |                   +---> stream_model_request_node()
    |                   |         +-- streaming_callback(delta)
    |                   |
    |                   +---> process_node()
    |                             |
    |                             +-- emit_tool_returns()
    |                             +-- record_thought()
    |                             +-- dispatch_tools()
    |                                     |
    |                                     +---> execute_tools_parallel()
    |                                               +-- tool_callback()
    |
    +---> _persist_run_messages()
```

## Key Files Reference

| File | Role |
|------|------|
| `main.py` | Entry point, orchestrator, main loop |
| `history_preparer.py` | Message history preparation and sanitization |
| `request_logger.py` | Logging utilities for request processing |
| `orchestrator/orchestrator.py` | Response node processing |
| `orchestrator/tool_dispatcher.py` | Tool extraction and dispatch |
| `tool_executor.py` | Parallel execution with retry |
| `streaming.py` | Token-level streaming |
| `response_state.py` | State machine |
| `state_transition.py` | Transition rules |
| `resume/sanitize.py` | History cleanup |

## Callbacks

The orchestrator accepts several callbacks for UI integration:

| Callback | Purpose |
|----------|---------|
| `streaming_callback` | Receives text deltas as tokens arrive |
| `tool_callback` | Called when a tool executes |
| `tool_result_callback` | Called with tool results for display |
| `tool_start_callback` | Called when tool names are identified |
| `notice_callback` | Called for user intervention notices |

## Design Principles

This architecture embodies tunacode's design philosophy:

- **Clear separation of concerns**: Each component has a single responsibility
- **Explicit state management**: State transitions are logged and tracked
- **Detailed instrumentation**: Debug logging throughout for visibility
- **Fail-fast error handling**: No silent fallbacks, errors propagate immediately
- **User informed**: Callbacks keep UI updated at every step
