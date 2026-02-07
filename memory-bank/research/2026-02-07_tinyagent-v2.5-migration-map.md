# Research — pydantic-ai → tinyAgent v2.5 Migration Map

**Date:** 2026-02-07
**Last updated:** 2026-02-07
**Owner:** agent
**Phase:** Research
**Status:** Phase 1 implemented (dependency + scaffold); remaining phases are mapping only

> tinyAgent v2.5 is vendored in this repo at `tinyAgent/` for reference.
> This document maps tunacode’s current pydantic-ai integration to tinyAgent’s event-driven API.

## Phase 1 (tun-00df) — completed

What landed:

- `pyproject.toml`: added `tinyagent` dependency + `[tool.uv.sources]` to install from repo-local `./tinyAgent` (editable).
- `uv.lock`: updated via `uv lock`.
- `src/tunacode/core/tinyagent/__init__.py`: small scaffolding module to fail fast if `tinyagent` is missing.

Verification:

- `uv sync`
- `uv run pytest`
- `uv run ruff check --fix .`

Repo hygiene (temporary):

- Pre-commit hooks exclude `tinyAgent/` for now (vendored upstream includes non-executable shebang scripts + Bandit-flagged examples).

## Goal

Full rip-and-replace:

- Replace pydantic-ai with tinyAgent v2.5.
- Consume tinyAgent events directly (no adapter layer that pretends to be pydantic-ai).
- tinyAgent owns tool-call extraction and tool execution.
- No backward compatibility for persisted pydantic-ai sessions.

Non-goals:

- Preserve tool parallelism (tinyAgent executes tools sequentially).
- Migrate old session JSON on disk.

---

## 1. Executive summary

### What changes architecturally

- **Old:** tunacode iterates pydantic-ai “nodes” and runs a custom orchestrator:
  `agent.iter() → process_node() → dispatch_tools() → execute_tools_parallel()`.
- **New:** tunacode iterates **tinyAgent events** and updates UI/state from those:
  `agent.stream() → handle_event(event)`.

### Primary deletions

- Delete the node-based orchestrator + tool dispatcher modules.
- Delete pydantic-ai shims and message/protocol types.

### Primary new work

- Implement a small event-handler layer in `core/agents/main.py`.
- Wrap tunacode tools as `tinyagent.AgentTool.execute`.
- Update message sanitization/persistence code to use tinyAgent message TypedDicts.

---

## 2. Locked decisions

1. **Direct event consumption (no compatibility adapter).**
2. **tinyAgent owns tool execution** (`execute_tool_calls()`), sequential is accepted.
3. **No backward compatibility** for old pydantic-ai sessions.

---

## 3. tinyAgent v2.5 API facts (verified against local `tinyAgent/` copy)

### 3.1 Core objects

- `tinyagent.Agent(AgentOptions(...))`
- Mutators:
  - `agent.set_model(Model(...))`
  - `agent.set_system_prompt(str)`
  - `agent.set_tools(list[AgentTool])`
  - `agent.replace_messages(list[AgentMessage])`
- Prompt loop:
  - `async for event in agent.stream(input_data)`

### 3.2 Messages (TypedDicts)

- `UserMessage`: `{role: "user", content: [...]}`
- `AssistantMessage`: `{role: "assistant", content: [...], stop_reason, usage, ...}`
- `ToolResultMessage`: `{role: "tool_result", tool_call_id, tool_name, content, is_error, details}`

Content blocks live under `AssistantMessage["content"]` with `type`:

- `{"type": "text", "text": ...}`
- `{"type": "thinking", "thinking": ...}`
- `{"type": "tool_call", "id": ..., "name": ..., "arguments": {...}}`

### 3.3 Events (dataclasses)

Key event types (string in `event.type`):

- `agent_start`, `turn_start`
- `message_start`, `message_update`, `message_end`
- `tool_execution_start`, `tool_execution_update`, `tool_execution_end`
- `turn_end`, `agent_end`

### 3.4 Tool execution call signature (important)

`AgentTool.execute` is typed as `Callable[..., Awaitable[AgentToolResult]]`, but **the call site is fixed**:

```python
# tinyAgent/tinyagent/agent_tool_execution.py
result = await tool.execute(tool_call_id, validated_args, signal, on_update)
```

So tunacode’s wrapper must accept 4 args:

1. `tool_call_id: str`
2. `args: dict` (validated)
3. `signal: asyncio.Event | None`
4. `on_update: Callable[[AgentToolResult], None]`

### 3.5 AgentEndEvent payload

- `AgentEndEvent.messages` contains **new messages produced in that run**, not the full conversation.
- Full conversation lives in `agent.state["messages"]` (Agent appends messages internally on `message_end`).

---

## 4. Known gaps / risks that affect the migration plan

### 4.1 Abort / cancellation semantics are currently weak upstream

Findings from local tinyAgent code:

- `Agent.abort()` sets an `asyncio.Event` passed into the loop as `signal`.
- `agent_loop.py` does **not** check `signal.is_set()`.
- Providers (`openrouter_provider.py`, `alchemy_provider.py`) do **not** check `options["signal"]` either.

Implication:

- “Abort” may only be observed after the current provider finishes streaming.

Plan impact:

- We likely need a tunacode-owned `stream_fn` wrapper (or upstream tinyAgent patch) that checks `signal.is_set()` inside the streaming loop and terminates early, producing a final assistant message with `stop_reason="aborted"`.

### 4.2 Tool retry semantics are not a first-class feature

tinyAgent treats tool exceptions as `is_error=True` tool results and continues the loop.
There is no explicit “retry” handshake.

Implication:

- Tunacode’s existing `ToolRetryError` must be translated into a tool result that *encourages* the model to call the tool again (error text), but there is no guarantee.

### 4.3 Usage field shape is provider-specific

`AssistantMessage["usage"]` is a `JsonObject`. Keys are not standardized.
Example observed in error-path: `{"input": 0, "output": 0, "cacheRead": 0, ...}`.

Plan impact:

- `normalize_request_usage()` must accept dicts and support multiple key variants.

---

## 5. Event → tunacode callback mapping

| tunacode callback | tinyAgent event | Notes |
|---|---|---|
| `tool_start_callback(label)` | `tool_execution_start` | `label` from `tool_name` |
| (remove) `tool_callback(...)` | n/a | tinyAgent owns tool execution |
| `tool_result_callback(name, status, args, result, duration)` | `tool_execution_end` | duration is not provided by tinyAgent; tunacode can measure locally if needed |
| `streaming_callback(delta)` | `message_update` with `assistant_message_event.type == "text_delta"` | use `assistant_message_event.delta` |
| `notice_callback(notice)` | n/a | keep internal-only |

---

## 6. File-by-file migration map

### 6.1 Delete (tinyAgent replaces these modules)

| File | Why |
|---|---|
| `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py` | node-based orchestration disappears |
| `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py` | tool dispatch is internal to tinyAgent |
| `src/tunacode/core/agents/agent_components/orchestrator/_tool_dispatcher_collection.py` | tool-call extraction is internal |
| `src/tunacode/core/agents/agent_components/orchestrator/_tool_dispatcher_registry.py` | replaced by event-driven updates |
| `src/tunacode/core/agents/agent_components/orchestrator/_tool_dispatcher_execution.py` | tool execution is internal |
| `src/tunacode/core/agents/agent_components/orchestrator/_tool_dispatcher_constants.py` | unused after deletes |
| `src/tunacode/core/agents/agent_components/orchestrator/tool_returns.py` | tool results are message-level in tinyAgent |
| `src/tunacode/core/agents/agent_components/orchestrator/usage_tracker.py` | usage comes from assistant message usage dict |
| `src/tunacode/core/agents/agent_components/streaming.py` | streaming logic replaced by event consumption |
| `src/tunacode/core/agents/agent_components/streaming_debug.py` | pydantic-ai specific |
| `src/tunacode/core/agents/agent_components/tool_executor.py` | tinyAgent executes tools |
| `src/tunacode/core/agents/agent_components/result_wrapper.py` | pydantic-ai run-handle wrapper |
| `src/tunacode/core/agents/agent_components/message_handler.py` | pydantic-ai dynamic imports |
| `src/tunacode/infrastructure/llm_types.py` | pydantic-ai shim layer |
| `scripts/pydantic_usage_report.py` | obsolete once pydantic-ai removed |
| `scripts/pydantic_usage_baseline.json` | obsolete |

### 6.2 Rewrite (core integration points)

#### A) `src/tunacode/core/agents/agent_components/agent_config.py` — agent factory

New responsibilities:

- Construct `tinyagent.Agent` with a tunacode-owned `stream_fn`.
- Convert tunacode model selection into `tinyagent.Model(provider, id, api, thinking_level)`.
- Wrap tunacode tools into `tinyagent.AgentTool`.

#### B) `src/tunacode/core/agents/main.py` — request loop

Rewrite to:

- Prepare history as `list[tinyagent.AgentMessage]`.
- Call `agent.replace_messages(history)`.
- Iterate: `async for event in agent.stream(user_text)`.
- Implement an event handler table in one place (no nested conditionals; early return).

#### C) `src/tunacode/tools/decorators.py` — tool wrapper

Remove the pydantic-ai `ModelRetry` bridge entirely.

Implement wrapper converting tunacode tool callables into `AgentTool.execute`.

Pseudo:

```python
def as_tinyagent_tool(tc_tool) -> AgentTool:
    async def execute(tool_call_id, args, signal, on_update):
        if signal and signal.is_set():
            raise RuntimeError("aborted")
        try:
            result = await tc_tool(**args)
            return AgentToolResult(content=[{"type": "text", "text": str(result)}])
        except ToolRetryError as e:
            # No first-class retry: return an error-shaped result that instructs the model.
            return AgentToolResult(
                content=[{"type": "text", "text": f"TOOL_RETRY: {e}"}],
                details={"tool_retry": True},
            )
    return AgentTool(name=..., description=..., parameters=..., execute=execute)
```

### 6.3 Update (message & persistence utilities)

- `src/tunacode/utils/messaging/adapter.py`
  - discriminate by `role` and content `type` (no `kind` / `part_kind`)
  - stop using `model_copy()`, use dict spread

- `src/tunacode/core/agents/history_preparer.py`
  - operate on tinyAgent `role` messages

- `src/tunacode/core/agents/resume/sanitize.py`
  - dangling tool-call detection uses assistant `ToolCallContent.id` vs subsequent `ToolResultMessage.tool_call_id`

- `src/tunacode/core/session/state.py`
  - `json.dumps(messages)` / `json.loads()`
  - fail loudly when old pydantic-ai sessions are loaded (explicit error)

- `src/tunacode/types/callbacks.py`
  - delete `ToolCallback` / pydantic-ai protocol types

- UI:
  - `src/tunacode/ui/app.py`, `src/tunacode/ui/headless/output.py`
  - remove pydantic-ai imports; rely on `msg.get("role") == "assistant"`

- `pyproject.toml`:
  - add tinyAgent dependency
  - later remove pydantic-ai

---

## 7. Migration order (implementation plan)

> Keep diffs small. Each phase should be its own commit set.

1. **Dependency phase**
   - Add tinyAgent dependency (keep pydantic-ai temporarily).
   - Prove imports and minimal `Agent()` construction in isolation.

2. **Tool wrapper phase**
   - Implement `AgentTool` wrappers for existing tunacode tools.
   - Update tool retry tests to drop `ModelRetry`.

3. **Agent factory phase**
   - Build `Agent` from tunacode config.
   - Ensure model selection and system prompt are wired.

4. **Event-loop phase**
   - Rewrite `core/agents/main.py` to consume events.
   - Keep existing UI callbacks; feed them from event handlers.

5. **Delete orchestrator phase**
   - Remove orchestrator/tool dispatcher modules.
   - Remove unused imports and dead code.

6. **Message format phase**
   - Update adapter/history/sanitize/canonical usage normalization.

7. **UI + callbacks phase**
   - Remove pydantic-ai types in UI layers.

8. **Persistence phase**
   - Switch to dict-based message serialization.
   - Add clear error for old sessions (no silent fallback).

9. **Test + cleanup phase**
   - Update failing tests.
   - Delete dispatcher coverage tests.

10. **Remove pydantic-ai phase**
   - Remove dependency and remaining shims.
   - Remove pydantic guardrail scripts.

---

## 8. Verification checklist (definition of done)

- `uv run pytest` passes.
- `uv run ruff check --fix .` produces no new issues.
- No new mypy errors introduced (do not increase baseline).
- Manual TUI run:
  - streaming text renders correctly
  - tool calls render (start + end)
  - abort stops the run in a user-visible way (even if provider abort is best-effort)
  - session save/load works for new-format sessions

---

## 9. Local reference

Key tinyAgent v2.5 files (vendored):

- `tinyAgent/tinyagent/agent.py` — `Agent`, `AgentOptions`, `stream()`
- `tinyAgent/tinyagent/agent_types.py` — message TypedDicts, events, `AgentTool`
- `tinyAgent/tinyagent/agent_loop.py` — event production, tool call flow
- `tinyAgent/tinyagent/agent_tool_execution.py` — tool execution + execute call signature
- `tinyAgent/tinyagent/openrouter_provider.py` — `stream_openrouter()`
- `tinyAgent/tinyagent/alchemy_provider.py` — `stream_alchemy_openai_completions()`
