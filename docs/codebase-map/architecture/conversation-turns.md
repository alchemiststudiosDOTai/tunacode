# Conversation Turn Flow

## Overview

This document maps how a conversation turn flows through the system from user input to agent response to UI display.

---

## Flow Diagram

```
USER INPUT
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. EDITOR SUBMISSION (UI Layer)                                 │
│    File: src/tunacode/ui/app.py                                 │
│    ├─ User types in Editor widget                               │
│    ├─ EditorSubmitRequested message posted                      │
│    ├─ on_editor_submit_requested() formats message              │
│    └─ request_queue.put(message)                                │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. REQUEST WORKER (UI Layer)                                    │
│    File: src/tunacode/ui/app.py                                 │
│    ├─ _request_worker() dequeues message                        │
│    ├─ Builds callbacks (streaming, tool, result, progress)      │
│    └─ Calls _process_request(message)                           │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. ORCHESTRATOR SETUP (Core Layer)                              │
│    File: src/tunacode/core/agents/main.py                       │
│    ├─ process_request() creates RequestOrchestrator             │
│    ├─ RequestContext(request_id=uuid[:8], max_iterations=15)    │
│    ├─ get_or_create_agent() - cached pydantic-ai agent          │
│    ├─ prune_old_tool_outputs() - trim history                   │
│    └─ Create ToolBuffer, ResponseState                          │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. AGENT ITERATION LOOP                                         │
│    File: src/tunacode/core/agents/main.py                       │
│                                                                 │
│    async with agent.iter(message, message_history) as run:      │
│        async for node in run:                                   │
│            ├─ Stream tokens via streaming_callback              │
│            ├─ process_node(node, ...)                           │
│            ├─ Track iteration count                             │
│            └─ Check early completion                            │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. NODE PROCESSING                                              │
│    File: src/tunacode/core/agents/agent_components/             │
│          orchestrator/orchestrator.py                           │
│                                                                 │
│    process_node() phases:                                       │
│    ├─ Phase 1: Transition to ASSISTANT state                    │
│    ├─ Phase 2: Emit tool returns (tool_result_callback)         │
│    ├─ Phase 3: Record thoughts (session.conversation.thoughts)  │
│    ├─ Phase 4: Update usage tracking (tokens)                   │
│    ├─ Phase 5: Dispatch tools (categorize → execute)            │
│    ├─ Phase 6: Detect truncation/emptiness                      │
│    └─ Phase 7: Transition to RESPONSE state                     │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. TOOL DISPATCH                                                │
│    File: src/tunacode/core/agents/agent_components/             │
│          orchestrator/tool_dispatcher.py                        │
│                                                                 │
│    dispatch_tools():                                            │
│    ├─ Categorize tools:                                         │
│    │   ├─ READ_ONLY: glob, grep, read_file, list_dir, web_fetch │
│    │   ├─ RESEARCH: research_codebase (subagent)                │
│    │   └─ WRITE/EXECUTE: bash, write_file, update_file          │
│    ├─ Register: tool_registry.register(tool_call_id, name, args)│
│    └─ Execute via tool_callback                                 │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. TOOL EXECUTION                                               │
│    File: src/tunacode/core/agents/agent_components/             │
│          tool_executor.py                                       │
│                                                                 │
│    execute_tools_parallel():                                    │
│    ├─ max_parallel = CPU count                                  │
│    ├─ Each tool: up to TOOL_MAX_RETRIES attempts                │
│    ├─ Non-retryable: UserAbortError, ModelRetry, ValidationError│
│    └─ Exponential backoff with jitter on failures               │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. UI CALLBACKS                                                 │
│    File: src/tunacode/ui/repl_support.py                        │
│                                                                 │
│    tool_callback:                                               │
│    ├─ Check if tool needs confirmation                          │
│    ├─ Show inline dialog if needed                              │
│    ├─ Execute tool via ToolHandler                              │
│    └─ Raise UserAbortError if denied                            │
│                                                                 │
│    tool_result_callback:                                        │
│    ├─ Update status bar (last action, edited files)             │
│    ├─ Truncate result (MAX_CALLBACK_CONTENT)                    │
│    └─ Post ToolResultDisplay to app                             │
│                                                                 │
│    streaming_callback:                                          │
│    ├─ Accumulate tokens                                         │
│    ├─ Throttle display (STREAM_THROTTLE_MS)                     │
│    └─ Update streaming panel                                    │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. MESSAGE PERSISTENCE                                          │
│    File: src/tunacode/core/agents/main.py                       │
│                                                                 │
│    After agent loop:                                            │
│    ├─ run_messages = agent_run.all_messages()                   │
│    ├─ external_messages = session.conversation.messages[baseline_count:]     │
│    ├─ merged = [*run_messages, *external_messages]              │
│    ├─ session.conversation.messages = merged                                 │
│    └─ session.update_token_count()                              │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. RESPONSE DISPLAY                                            │
│    File: src/tunacode/ui/app.py                                 │
│                                                                 │
│    _process_request() completion:                               │
│    ├─ Render final response panel                               │
│    ├─ Include token count and duration                          │
│    ├─ Write to rich_log                                         │
│    ├─ Update resource bar                                       │
│    └─ Save session to disk                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## State Transitions

The `ResponseState` state machine tracks progress through each turn:

```
AgentState.USER_INPUT
    │ can_transition_to(ASSISTANT)
    ▼
AgentState.ASSISTANT
    │ process thoughts, usage, text content
    │ can_transition_to(TOOL_EXECUTION) or can_transition_to(RESPONSE)
    ▼
AgentState.TOOL_EXECUTION
    │ dispatch and execute tools
    │ can_transition_to(RESPONSE)
    ▼
AgentState.RESPONSE
    │ mark iteration complete
    │ can transition back to ASSISTANT if not task_completed
    └─────────────────────────────────────────────────────────────┐
                                                                  │
    (loop back if more iterations needed)                         │
    ◀─────────────────────────────────────────────────────────────┘
```

**File:** `src/tunacode/core/agents/agent_components/response_state.py`

---

## Data Structures

### Message Chain

```
User Text (str)
    │
    ▼
Formatted with timestamp
    │
    ▼
Queued as string
    │
    ▼
process_request(message: str)
    │
    ▼
SessionState.messages (pydantic-ai message history)
    │
    ▼
ModelRequest / ModelResponse objects
    │
    ▼
Persisted after agent completes
```

### Message Types (pydantic-ai)

| Type | Purpose |
|------|---------|
| `ModelRequest` | User input or tool returns sent to LLM |
| `ModelResponse` | LLM response with text and/or tool calls |
| `ToolCallPart` | Tool call request (name, id, args) |
| `ToolReturnPart` | Tool execution result |
| `SystemPromptPart` | System messages |
| `UserPromptPart` | User messages |

**File:** `src/tunacode/types/pydantic_ai.py`

### Tool Call Storage

```python
# Normalized and stored during dispatch
session.runtime.tool_registry: ToolCallRegistry
# Maps tool_call_id → CanonicalToolCall (args + lifecycle)
# Retrieved when tool result returns
```

### Session State

```python
@dataclass
class SessionState:
    messages: MessageHistory      # pydantic-ai messages
    thoughts: list[str]           # thoughts outside history
    tool_registry: ToolCallRegistry  # tool call lifecycle + args
```

**File:** `src/tunacode/core/state.py`

---

## Callback Types

| Callback | Signature | Purpose |
|----------|-----------|---------|
| `streaming_callback` | `async (str) → None` | Token-by-token streaming |
| `tool_callback` | `async (ToolCallPart, node) → None` | Tool execution |
| `tool_result_callback` | `(name, status, args, result, duration_ms) → None` | Result display |
| `tool_start_callback` | `(str) → None` | Tool start notification |
| `tool_progress_callback` | `(str) → None` | Subagent progress |

**File:** `src/tunacode/types/callbacks.py`

---

## Request Context

Each request gets a unique context:

```python
@dataclass(slots=True)
class RequestContext:
    request_id: str      # UUID truncated to 8 chars
    max_iterations: int  # From config (default 15)
    debug_metrics: bool  # Enable detailed logging
```

**File:** `src/tunacode/core/agents/main.py:62`

---

## Message Invariants

These invariants MUST hold for the conversation to be valid:

### 1. Tool Call Pairing

Every `ModelResponse` with tool_calls MUST be followed by matching `ToolReturn(s)` before any new `ModelRequest`.

```
VALID:
  ModelResponse(tool_calls=[A, B])
  ToolReturn(A)
  ToolReturn(B)
  ModelRequest(...)  ✓

INVALID:
  ModelResponse(tool_calls=[A, B])
  ModelRequest(...)  ✗ API will reject - missing tool returns
```

**Enforcement:** `_remove_dangling_tool_calls()` cleans up on `UserAbortError`.

### 2. Exception Safety

Any exception path that exits the agent loop must restore message history to a valid state. The `except UserAbortError` handler in `RequestOrchestrator._run_impl()` calls `_remove_dangling_tool_calls()` to enforce invariant #1.

### 3. Message Order

Messages must follow the pattern:
```
[SystemPrompt?] [UserPrompt | ToolReturn]+ [ModelResponse]+
```

The agent loop naturally maintains this. Violations indicate a bug.

---

## Critical Behaviors

### Empty Response Handling

- Tracks consecutive empty responses
- After 1+ consecutive empty: `empty_handler.should_intervene()`
- Calls `handle_empty_response()` to synthesize guidance
- Prevents infinite loops of no-op iterations

### Tool Call Resolution

1. Part has unique `tool_call_id`
2. Args parsed and stored in `tool_registry`
3. Tool executed via callback
4. When result returns, args retrieved and consumed
5. All results accumulated for next LLM request

### Session Persistence

After each request:
1. Messages merged from agent run and external sources
2. Token count updated
3. Session saved to disk
4. On reload: `_replay_session_messages()` renders prior conversation

---

## Key Files

| Layer | File | Responsibility |
|-------|------|----------------|
| UI | `ui/app.py` | TextualReplApp - lifecycle, queue, callbacks |
| UI | `ui/repl_support.py` | Callback builders, confirmation state |
| UI | `ui/renderers/agent_response.py` | Final response panel rendering |
| Core | `core/agents/main.py` | RequestOrchestrator - main loop |
| Core | `core/agents/agent_components/orchestrator/orchestrator.py` | process_node() |
| Core | `core/agents/agent_components/orchestrator/tool_dispatcher.py` | Tool dispatch |
| Core | `core/agents/agent_components/tool_executor.py` | Parallel execution, retries |
| Core | `core/agents/agent_components/streaming.py` | Token streaming |
| Core | `core/agents/agent_components/response_state.py` | State machine |
| State | `core/state.py` | SessionState - history, thoughts, tool calls |
| Types | `types/pydantic_ai.py` | Message type wrappers |
| Types | `types/callbacks.py` | Callback signatures |

---

## Example Round-Trip

User: "find all grep calls in src/"

```
1. Editor captures input
2. Message queued: "find all grep calls in src/"
3. _process_request() builds callbacks
4. RequestOrchestrator created:
   - request_id="a3b2c1d0"
   - max_iterations=15
5. agent.iter() starts

   Iteration 1: Tokens stream "I'll search for grep..."
   - streaming_callback() updates panel

   Iteration 2: ModelResponseNode
   - Parts: [TextPart("I found..."), ToolCallPart(grep, args)]
   - dispatch_tools() categorizes grep as READ_ONLY
   - tool_callback() confirms and executes
   - Results: 15 matches found
   - tool_result_callback() renders result panel

   Iteration 3: ToolReturnNode
   - Tool result passed back to agent

   Iteration 4: ModelResponseNode
   - Agent synthesizes final response
   - task_completed = True, early exit

6. Post-iteration:
   - Messages merged to session.conversation.messages
   - Final response panel rendered
   - Session saved to disk
```

---

**Generated:** 2026-01-17
