# TunaCode Agent Loop Ontology (Single Source of Truth)

**Status:** authoritative *as implemented in code* (not aspirational).

**Scope:** This document describes the **current** request/iteration loop and the **node orchestrator** (tool dispatch + tool returns + usage/thought recording) so the system can be replaced cleanly.

**Source of truth:** code only.

Primary code locations:

- Request loop (per user message): `src/tunacode/core/agents/main.py`
  - `RequestOrchestrator` (class)
  - `process_request(...)` (function)
- Node orchestrator (per streamed node): `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py`
  - `process_node(...)` (function)
- Tool dispatch pipeline:
  - `dispatch_tools(...)`: `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`
  - collection/normalization: `.../orchestrator/_tool_dispatcher_collection.py`, `.../_tool_dispatcher_registry.py`
  - execution + retries: `.../orchestrator/_tool_dispatcher_execution.py`, `src/tunacode/core/agents/agent_components/tool_executor.py`
- Tool return handling: `emit_tool_returns(...)`: `.../orchestrator/tool_returns.py`
- Streaming instrumentation: `stream_model_request_node(...)`: `src/tunacode/core/agents/agent_components/streaming.py`
- State contracts:
  - `StateManagerProtocol`: `src/tunacode/core/types/state.py`
  - runtime structures: `src/tunacode/core/types/state_structures.py`
  - tool lifecycle registry: `src/tunacode/core/types/tool_registry.py`

---

## 0) Terminology (Ontology)

### Concepts (nouns)

**Request**
- A single user message processed by `process_request(...)`.

**Run handle / AgentRun**
- The object returned by `pydantic_ai.Agent.iter(...)` context manager.
- Treated as `Any` via `tunacode.infrastructure.llm_types.AgentRun = Any`.
- Must support at least:
  - async iteration yielding **Nodes**
  - `.ctx` (used for streaming)
  - `.all_messages()` (used for persistence)

**Node**
- One element yielded by `async for node in run_handle:`.
- Structural contract is defined by *attributes accessed by TunaCode* (see §4).

**Session**
- The mutable runtime state behind `StateManagerProtocol.session`.

**Tool registry**
- `session.runtime.tool_registry: ToolCallRegistry`
- The single source of truth for tool call lifecycle tracking.

**ResponseState**
- `tunacode.core.agents.agent_components.response_state.ResponseState`
- A state machine wrapper used for UI/flow tracking (USER_INPUT → ASSISTANT → TOOL_EXECUTION → RESPONSE).

### Processes (verbs)

**Request loop**
- The outer orchestration of an agent run for a single user request.

**Node orchestration**
- The per-node processing step that:
  - consumes tool returns from the node request
  - records thought
  - updates usage
  - dispatches tool calls
  - transitions response state

---

## 1) Public Replacement Surface (what you must preserve)

If you want to replace the agent loop implementation/framework, you must preserve the observable behavior of these public surfaces:

### 1.1 `process_request(...)`
**Location:** `src/tunacode/core/agents/main.py`

```py
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
    ...
```

#### Input contract
- `message: str`
  - user’s prompt for this request.
- `model: ModelName` (`ModelName = str`)
  - model selector string consumed by `get_or_create_agent(...)` (see §2.2).
- `state_manager: StateManagerProtocol`
  - must provide `.session` containing at least the fields referenced in §3.
- callbacks (optional)
  - `tool_callback`: invoked for each tool call batch item (see §5.3)
  - `streaming_callback`: invoked with streaming text deltas (see §5.1)
  - `tool_start_callback`: called once per dispatched batch (best-effort UI signal)
  - `tool_result_callback`: called once per tool return observed in the next request
  - `notice_callback`: called when empty-response intervention triggers

#### Output contract
- Returns an `AgentRun` (framework object) **wrapped** with `.response_state`:
  - actual returned type is `tunacode.core.agents.agent_components.result_wrapper.AgentRunWithState`
  - it delegates all attributes to the underlying run handle and adds:

```py
run.response_state  # ResponseState
```

#### Side effects (authoritative)
- Mutates `state_manager.session.*` (details in §3)
- Updates `session.conversation.messages` to the run’s authoritative messages at end of run
- Updates `session.conversation.thoughts`
- Updates `session.usage.last_call_usage` and accumulates totals
- Updates `session.runtime.tool_registry` during tool call/return lifecycle

#### Exceptions
- May raise (non-exhaustive):
  - `GlobalRequestTimeoutError` (if global timeout enabled)
  - `UserAbortError` (propagated)
  - `asyncio.CancelledError` (propagated)
  - framework/network/tool exceptions not caught by outer loop

### 1.2 Node orchestration entry point: `process_node(...)`
**Location:** `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py`

```py
async def process_node(
    node: Any,
    tool_callback: ToolCallback | None,
    state_manager: StateManagerProtocol,
    _streaming_callback: StreamingCallback | None = None,
    response_state: ResponseState | None = None,
    tool_result_callback: ToolResultCallback | None = None,
    tool_start_callback: ToolStartCallback | None = None,
) -> tuple[bool, str | None]:
    ...
```

#### Output contract
- Returns `(is_empty: bool, reason: str | None)`.
  - `is_empty=True` means the model response had **no non-empty text** and **no structured tool calls**.
  - `reason` is currently either `"empty"` or `None`.

---

## 2) Execution Model (what happens)

### 2.1 UI → core loop
**Typical caller:** `src/tunacode/ui/app.py` calls `process_request(...)` inside an `asyncio.Task`.

The agent loop is designed so UI can:
- render tool start events (`tool_start_callback`)
- render tool results as they come back (`tool_result_callback`)
- (optionally) stream deltas (`streaming_callback`)—currently passed as `None` by the Textual UI.

### 2.2 Agent creation + caching
**Location:** `src/tunacode/core/agents/agent_components/agent_config.py`

- `get_or_create_agent(model, state_manager)` is the only constructor path.
- Caches agents in:
  - session cache: `session.agents[model]` and `session.agent_versions[model]`
  - module cache: `tunacode.infrastructure.cache.caches.agents`
- Agent version hash is computed from:
  - `settings.max_retries`
  - `settings.tool_strict_validation`
  - request delay
  - `settings.global_request_timeout`

**System prompt composition (as implemented):**
1) load `src/tunacode/prompts/system_prompt.md`
2) append a context file from CWD (default: `AGENTS.md`) via `load_tunacode_context()`

### 2.3 Message history preparation
**Location:** `src/tunacode/core/agents/history_preparer.py`

Before calling into the framework, the loop:
- prunes old tool outputs for token budget (`prune_old_tool_outputs`)
- runs cleanup loop to remove inconsistencies (`run_cleanup_loop`)
- drops a trailing "request" message to avoid consecutive requests
- sanitizes history for resume (`sanitize_history_for_resume`)

Output:
- `message_history: list[Any]` passed to `agent.iter(..., message_history=...)`
- `baseline_message_count: int` used later to preserve messages externally appended during run

### 2.4 Outer request loop (per request)
**Location:** `src/tunacode/core/agents/main.py`

Control flow:

1) `RequestOrchestrator.run()`
   - applies global timeout (if enabled via session config)
2) `_run_impl()`
   - initializes request context + resets per-run fields
   - gets or creates an agent
   - prepares history
   - enters framework iteration context: `async with agent.iter(...) as run_handle:`
3) `_run_agent_iterations(...)`
   - iterates nodes with `async for node in run_handle:`
   - for each node calls `_handle_iteration_node(...)`
4) on completion:
   - persists run messages into `session.conversation.messages`

**Important: `max_iterations` is currently NOT enforced.**
- `RequestContext.max_iterations` is computed and stored but never checked in the loop.

### 2.5 Per-node iteration
**Location:** `src/tunacode/core/agents/main.py` (`_handle_iteration_node`)

Per node:
1) update runtime counters:
   - `runtime.current_iteration = iteration_index`
   - `runtime.iteration_count = iteration_index`
2) optional streaming:
   - if `streaming_callback` and `Agent.is_model_request_node(node)` then
     `stream_model_request_node(...)`
3) node orchestration:
   - calls `process_node(...)`
4) empty response handling:
   - if empty, triggers `handle_empty_response(...)` and `notice_callback(...)`
5) completion:
   - stops early only if `response_state.task_completed` is set `True`

---

## 3) State & Side-Effects Contract (StateManager / Session)

This section is essential for replacement: **the loop is not pure**; it encodes state mutations that callers (UI) rely on.

### 3.1 Fields reset per request
**Location:** `RequestOrchestrator._reset_session_state()`

Mutations:
- `runtime.current_iteration = 0`
- `runtime.iteration_count = 0`
- `runtime.tool_registry.clear()`
- `runtime.batch_counter = 0`
- `runtime.consecutive_empty_responses = 0`
- `session.task.original_query = ""` then immediately set to `message` (see below)

### 3.2 Request identity
- `runtime.request_id` is set to the first 8 chars of a UUID4.

### 3.3 Original query
- Intended to be set once, but as implemented it is effectively set every request:
  - `_reset_session_state()` clears it
  - `_set_original_query_once()` then sets it to the request message

### 3.4 Conversation persistence rules
**Location:** `RequestOrchestrator._persist_run_messages(...)`

At run end:
- `run_messages = list(run_handle.all_messages())`
- `external_messages = conversation.messages[baseline_message_count:]`
- `conversation.messages = run_messages + external_messages`

Meaning:
- the run handle is the *authoritative* source for messages during the run
- any messages appended externally during the run after baseline are preserved

### 3.5 Tool registry lifecycle
**Location:** `core/types/tool_registry.py` + tool dispatcher + tool returns

Observed lifecycle:
1) tool call discovered → `tool_registry.register(tool_call_id, tool_name, args)`
2) about to execute → `tool_registry.start(tool_call_id)`
3) later tool return observed in a subsequent model request → `tool_registry.complete(tool_call_id, result)`
4) on execution failure → `tool_registry.fail(tool_call_id, error)`
5) on user abort during execution → `tool_registry.cancel(tool_call_id, reason)`

Invariant:
- Tool return consumption relies on the args being registered by tool_call_id.
  - tool returns call `consume_tool_call_args(...)`
  - it raises if args are missing.

### 3.6 Usage tracking
**Location:** `.../orchestrator/usage_tracker.py`

- On each node with `model_response`, usage is normalized and:
  - `session.usage.last_call_usage = UsageMetrics(...)`
  - `session.usage.session_total_usage.add(last_call_usage)`

### 3.7 Streaming debug state
**Location:** `.../agent_components/streaming.py`

On stream start:
- `session._debug_raw_stream_accum` reset to `""`
- `session._debug_events` reset to `[]`

Streaming callback is invoked with text deltas; deltas are appended to `_debug_raw_stream_accum`.

---

## 4) Structural Contracts (framework objects treated as `Any`)

Because `pydantic_ai` types are mostly typed as `Any` in `tunacode.infrastructure.llm_types`, TunaCode relies on **structural typing**.

### 4.1 Node: minimum attributes used by TunaCode
A node is any object with some/all of:

- `node.request: Any | None`
  - when present, `request.parts` is iterated for tool-return parts
- `node.model_response: Any | None`
  - when present, `model_response.parts: list[Any]` is read
  - `model_response.usage` is passed to usage normalization
- `node.thought: str | None`
  - when present, appended to `session.conversation.thoughts`
- `node.result: Any | None`
  - when present, `node.result.output` is read to detect user-visible output

Optional streaming capability:
- `node.stream(agent_run_ctx)` must be an async context manager that yields an async iterator of events.

### 4.2 Message parts: minimum attributes used
For response parts (`model_response.parts`) and request parts (`request.parts`):

- `part.part_kind: str`
  - tool calls: `"tool-call"`
  - tool returns: `"tool-return"`
  - text: `"text"`
- `part.content: Any` (text/tool return content)
- Tool call specific:
  - `part.tool_call_id: str | None`
  - `part.tool_name: str | None`
  - `part.args: str | dict | None`

---

## 5) Callback Contracts (inputs/outputs/failure behavior)

### 5.1 `StreamingCallback`
**Type:** `Callable[[str], Awaitable[None]]`

Contract:
- Called with ordered text deltas.
- If it raises, the streaming path raises and the request fails.

### 5.2 `ToolResultCallback`
**Type:** `Callable[[ToolName, str, ToolArgs, str | None, float | None], None]`

Called when:
- tool-return parts are observed in `node.request.parts`.

Arguments:
- `tool_name`: tool name from tool-return part (string)
- `status`: always `"completed"` in current emitter
- `args`: resolved from tool registry by `tool_call_id`
- `result`: stringified tool return content
- `duration_ms`: always `None` in current emitter

Failure behavior:
- Exceptions propagate (no try/except around callback).

### 5.3 `ToolCallback` (tool execution hook)
**Type:** `Callable[[ToolCallPartProtocol, StreamResultProtocol], Awaitable[None]]`

Where called:
- `dispatch_tools(...)` collects tool call parts and then executes them through `execute_tools_parallel(...)`, which calls the callback once per tool call.

Semantics:
- The callback is the “executor” for the tool call part in the context of the current node.
- If it raises:
  - retry logic may retry unless the exception is non-retryable (see `NON_RETRYABLE_ERRORS` in `tool_executor.py`).
  - ultimate failure is recorded in the tool registry (`fail(...)` or `cancel(...)`).

### 5.4 `ToolStartCallback`
**Type:** `Callable[[str], None]`

Called when:
- a batch of tool calls is about to execute.

Argument:
- a display string of up to N tool names, with a suffix if truncated.

### 5.5 `NoticeCallback`
**Type:** `Callable[[str], None]`

Called when:
- an iteration response is detected as empty.

Argument:
- a generated user-facing notice string.

---

## 6) Abort / Timeout / Cleanup Semantics

### 6.1 Global request timeout
**Location:** `RequestOrchestrator.run()`

- timeout is computed via `_coerce_global_request_timeout(session)`.
- when triggered:
  - agent cache is invalidated (`invalidate_agent_cache(model, state_manager)`)
  - raises `GlobalRequestTimeoutError(timeout)`

### 6.2 Abort / cancellation cleanup
**Location:** `RequestOrchestrator._handle_abort_cleanup()`

If `UserAbortError` or `asyncio.CancelledError` bubbles up:

1) If `session._debug_raw_stream_accum` has partial streamed text, append a synthetic interrupted `ModelResponse` to conversation history.
2) Sanitize message history:
   - remove dangling tool calls
   - remove empty responses
   - remove consecutive requests
3) Invalidate the agent cache for the model.

---

## 7) Replaceability Checklist (what a new engine must provide)

To replace the current implementation cleanly, implement an adapter that provides the same *structural contracts* and side effects:

### 7.1 Engine must support
- async context manager “run handle”
- async iteration over “nodes”
- per node:
  - tool return parts reachable at `node.request.parts`
  - response parts reachable at `node.model_response.parts`
  - optional thought string
  - optional final output at `node.result.output`
- run handle must provide `all_messages()` to persist history

### 7.2 Tool loop integration must preserve
- tool call discovery (structured + fallback from text)
- tool registry registration/args normalization keyed by `tool_call_id`
- tool return consumption using `tool_call_id` → args mapping

### 7.3 State updates must preserve
- session runtime counters and request_id
- conversation messages persistence strategy (authoritative run messages + preserve external appends)
- usage metrics updates

---

## 8) Index of Relevant Files (for code navigation)

- `src/tunacode/core/agents/main.py`
  - `RequestOrchestrator`
  - `EmptyResponseHandler`
  - `_handle_iteration_node`
- `src/tunacode/core/agents/history_preparer.py`
- `src/tunacode/core/agents/agent_components/agent_config.py`
- `src/tunacode/core/agents/agent_components/streaming.py`
- `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py`
- `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`
- `src/tunacode/core/agents/agent_components/orchestrator/tool_returns.py`
- `src/tunacode/core/agents/agent_components/tool_executor.py`
- `src/tunacode/core/types/state.py`
- `src/tunacode/core/types/state_structures.py`
- `src/tunacode/core/types/tool_registry.py`
