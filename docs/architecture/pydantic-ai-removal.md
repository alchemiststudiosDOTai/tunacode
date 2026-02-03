---
summary: |
  Migration plan to replace pydantic-ai with TinyAgent.

  Validated against the repository state on 2026-02-03.

  Key facts (current tree):
  - Delete ~1.6k lines of pydantic-ai integration glue (6 files, 1,639 LOC).
  - Keep ~2.9k lines of framework-agnostic business logic (18 files, 2,866 LOC).
  - The largest *real* work item is rewriting the agent loop in
    src/tunacode/core/agents/main.py (currently pydantic-ai-driven).

when_to_read:
  - Planning the pydantic-ai removal
  - Understanding what code depends on pydantic-ai
  - Identifying reusable components for TinyAgent
  - Estimating migration effort

ontology:
  dead_files:
    description: Files deleted when pydantic-ai removed
    total_lines: 1639
    files:
      - src/tunacode/core/agents/agent_components/agent_config.py
      - src/tunacode/core/agents/agent_components/streaming.py
      - src/tunacode/core/agents/agent_components/streaming_debug.py
      - src/tunacode/core/agents/agent_components/openai_response_validation.py
      - src/tunacode/core/agents/agent_components/response_state.py
      - src/tunacode/core/agents/agent_components/state_transition.py

  rewrite_files:
    description: Files that remain but must be rewritten to remove pydantic-ai semantics
    primary:
      - src/tunacode/core/agents/main.py

  refactor_files:
    description: Files needing focused type/import/serialization swaps
    patterns:
      - replace ModelRetry with ToolRetryError
      - replace pydantic-ai message types with canonical message types
      - replace pydantic-ai serialization with canonical adapters
      - replace isinstance checks with duck-typed / attribute checks

  keep_files:
    description: Reusable framework-agnostic code
    total_lines: 2866
    modules:
      - src/tunacode/core/agents/resume/
      - src/tunacode/core/types/
      - src/tunacode/types/
      - src/tunacode/exceptions.py
      - src/tunacode/constants.py
---

# pydantic-ai Removal Migration Plan

This document maps the migration path from pydantic-ai to TinyAgent for the tunacode agent loop.

## Executive Summary (validated 2026-02-03)

| Category | Lines | Action |
|----------|-------|--------|
| DEAD | 1,639 | Delete with pydantic-ai |
| REWRITE | 640 (main.py) | Replace pydantic-ai-driven loop with TinyAgent loop |
| REFACTOR | (small, scattered) | Swap types/imports/serialization |
| KEEP | 2,866 | Reuse as-is |

Note: The previous “Net -1,600” estimate is not reliable until the `main.py` rewrite lands (it can go up or down depending on TinyAgent wiring).

## Repository Footprint (reality check)

As of 2026-02-03, these files contain the string `pydantic_ai` and are in-scope for the migration:

- `src/tunacode/core/agents/agent_components/agent_config.py`
- `src/tunacode/core/agents/agent_components/message_handler.py`
- `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`
- `src/tunacode/core/agents/agent_components/streaming.py`
- `src/tunacode/core/agents/agent_components/tool_executor.py`
- `src/tunacode/core/agents/main.py`
- `src/tunacode/core/agents/resume/summary.py` (TYPE_CHECKING-only import)
- `src/tunacode/core/state.py`
- `src/tunacode/exceptions.py` (documentation reference)
- `src/tunacode/infrastructure/llm_types.py`
- `src/tunacode/tools/decorators.py`
- `src/tunacode/tools/parsing/tool_parser.py` (documentation reference)
- `src/tunacode/types/canonical.py` (comment reference)
- `src/tunacode/ui/app.py`
- `src/tunacode/ui/headless/output.py`

## Why Migrate

1. **Own the loop** - Debug issues without framework black boxes
2. **Less glue** - Delete ~1.6k LOC of integration scaffolding
3. **Simpler abstractions** - TinyAgent’s event-driven model should map cleanly to our UI callbacks
4. **Steering/follow-up** - TinyAgent supports mid-execution interrupts

## DEAD Files (Delete)

These files exist solely for pydantic-ai integration. Delete when removing the dependency.

(LOC counts below are current `wc -l` numbers.)

### agent_config.py (457 lines)

**Location:** `src/tunacode/core/agents/agent_components/agent_config.py`

**pydantic-ai imports:**
```python
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig
from pydantic_ai.settings import ModelSettings
```

**Exports:**
- `get_or_create_agent()` - Creates pydantic-ai Agent instances
- `invalidate_agent_cache()` - Clears agent cache
- `get_agent_tool()` - Returns Agent and Tool classes

**Imported by:**
- `agent_components/__init__.py`
- `core/agents/main.py`
- `ui/commands/__init__.py`

---

### streaming.py (302 lines)

**Location:** `src/tunacode/core/agents/agent_components/streaming.py`

**pydantic-ai imports:**
```python
from pydantic_ai.messages import PartDeltaEvent, TextPartDelta
```

**Purpose:** Streams token deltas from pydantic-ai’s `node.stream()` API.

**Exports:**
- `stream_model_request_node()` - Main streaming function

**Replacement:** TinyAgent streaming/event APIs.

---

### streaming_debug.py (372 lines)

**Location:** `src/tunacode/core/agents/agent_components/streaming_debug.py`

**pydantic-ai imports:** None directly, but tightly coupled to `streaming.py`.

**Purpose:** Debug instrumentation for streaming events.

**Fate:** Dies with `streaming.py`.

---

### openai_response_validation.py (267 lines)

**Location:** `src/tunacode/core/agents/agent_components/openai_response_validation.py`

**pydantic-ai imports:** None directly, but wired into pydantic-ai client configuration via `agent_config.py`.

**Purpose:** HTTP response validation hook for OpenAI chat completions.

**Exports:**
- `validate_openai_chat_completion_response()` - Async response hook

**Replacement:** TinyAgent providers (or our provider adapters) own validation.

---

### response_state.py (129 lines)

**Location:** `src/tunacode/core/agents/agent_components/response_state.py`

**Purpose:** Tracks agent state during the pydantic-ai `async for node in run_handle` loop.

**Exports:**
- `ResponseState` class - state tracking dataclass

**Replacement:** TinyAgent’s state/events. (Do not carry over the pydantic-ai state machine.)

---

### state_transition.py (112 lines)

**Location:** `src/tunacode/core/agents/agent_components/state_transition.py`

**Purpose:** State machine for agent response processing states.

**Exports:**
- `InvalidStateTransitionError`
- `StateTransitionRules`
- `AgentStateMachine`
- `AGENT_TRANSITION_RULES`

**Replacement:** TinyAgent manages state internally; we should keep only UI-facing state we truly need.

---

## REWRITE Files (Replace loop semantics)

### core/agents/main.py (640 lines)

**Location:** `src/tunacode/core/agents/main.py`

This is the center of gravity for the migration:
- It imports `pydantic_ai.Agent` and pydantic-ai message types.
- It is wired to the existing `agent_components` (streaming + response_state + tool orchestration).

**Plan:** Keep the public interface (`process_request`, etc.) but rewrite the internal loop to:
- run TinyAgent instead of pydantic-ai
- emit the same callback events the UI expects
- preserve resume/sanitize behavior

This file being “only 640 lines” does not mean it is trivial—it encodes runtime semantics.

---

## REFACTOR Files (Swap Types / Imports / Serialization)

These files use pydantic-ai types or APIs and need focused changes.

### Critical: ModelRetry → ToolRetryError

Used for tool retry signaling:

| File | Current | Replacement |
|------|---------|-------------|
| `src/tunacode/core/agents/agent_components/tool_executor.py` | `from pydantic_ai import ModelRetry` | `from tunacode.exceptions import ToolRetryError` |
| `src/tunacode/tools/decorators.py` | `from pydantic_ai.exceptions import ModelRetry` | `from tunacode.exceptions import ToolRetryError` |

**Pattern change:**
```python
# Before
from pydantic_ai import ModelRetry
raise ModelRetry("hint message")

# After
from tunacode.exceptions import ToolRetryError
raise ToolRetryError("hint message")
```

---

### isinstance Checks: replace type-based dispatch

Replace type-based dispatch with duck-typed / canonical-message checks.

Current touchpoints:
- `src/tunacode/ui/app.py` imports `pydantic_ai.messages.ModelResponse` inside functions and uses `isinstance`.
- `src/tunacode/ui/headless/output.py` imports `ModelResponse` and uses `isinstance`.

Recommended replacement pattern:
```python
if getattr(msg, "kind", None) == "response":
    ...
```

(Exact predicate depends on what canonical/TinyAgent message shape we standardize on.)

---

### tool_dispatcher.py: ToolCallPart + ResponseState coupling

**Location:** `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`

This file is *not* just a one-line import swap:
- It constructs `ToolCallPart` (currently imported from `pydantic_ai.messages` in-function).
- It is coupled to `ResponseState` (which is scheduled for deletion).

**Plan:**
- Replace tool-call construction with our canonical `ToolCallPart` (`src/tunacode/types/canonical.py`).
- Remove/replace `ResponseState` usage (either wire to TinyAgent events or a minimal internal runtime state).

---

### core/state.py: serialization

**Location:** `src/tunacode/core/state.py`

Current:
```python
from pydantic_ai.messages import ModelMessage
TypeAdapter(ModelMessage).dump_python(msg, mode="json")
```

Replacement:
- Prefer canonical message conversion (`to_canonical()` / `from_canonical()` via `tunacode.utils.messaging.adapter`), then serialize canonical.

---

### message_handler.py: dynamic import of pydantic_ai.messages

**Location:** `src/tunacode/core/agents/agent_components/message_handler.py`

Current behavior dynamically imports `pydantic_ai.messages` and provides fallback `SystemPromptPart`.

Replacement:
- Import canonical message classes directly.
- If a fallback is needed, implement it in our own types module (fail loud if we cannot construct required message shapes).

---

### infrastructure/llm_types.py: framework re-exports

**Location:** `src/tunacode/infrastructure/llm_types.py`

This is explicitly pydantic-ai-specific. Once the migration lands:
- either delete this module, or
- replace it with TinyAgent types, or
- make it a strict adapter layer with *no* re-exports used by core/ui.

---

## KEEP Files (Reusable)

These are framework-agnostic (or already duck-typed) and should remain mostly unchanged.

(LOC counts below are current `wc -l` numbers.)

### core/agents/resume/ Module (1,276 lines)

| File | Lines | Purpose | TinyAgent Compatible |
|------|------:|---------|---------------------|
| `prune.py` | 285 | Token management via backward-scan | Yes - accepts `list[Any]` |
| `filter.py` | 76 | History filtering at checkpoints | Yes |
| `summary.py` | 202 | Rolling summary generation | Yes (TYPE_CHECKING pydantic-ai import only) |
| `sanitize.py` | 564 | Message history cleanup | Yes - duck typed |
| `sanitize_debug.py` | 149 | Debug logging | Yes |

---

### Agent Components (283 lines)

| File | Lines | Purpose | TinyAgent Compatible |
|------|------:|---------|---------------------|
| `agent_helpers.py` | 131 | Tool descriptions, empty response | Yes |
| `truncation_checker.py` | 37 | Content truncation detection | Yes |
| `result_wrapper.py` | 51 | Result wrappers | Yes - uses `Any` |
| `orchestrator/usage_tracker.py` | 56 | Token/cost tracking | Yes |
| `orchestrator/message_recorder.py` | 8 | Thought recording | Yes |

---

### Types (804 lines)

| File | Lines | Purpose | TinyAgent Compatible |
|------|------:|---------|---------------------|
| `core/types/agent_state.py` | 26 | AgentState enum | Yes |
| `core/types/tool_registry.py` | 189 | Tool call lifecycle | Yes |
| `core/types/state.py` | 105 | Protocol definitions | Yes |
| `core/types/state_structures.py` | 70 | State dataclasses | Yes |
| `types/callbacks.py` | 94 | Callback protocols | Yes |
| `types/canonical.py` | 320 | Canonical message types | Yes |

---

### Shared (503 lines)

| File | Lines | Purpose | TinyAgent Compatible |
|------|------:|---------|---------------------|
| `exceptions.py` | 325 | Exception hierarchy | Yes |
| `constants.py` | 178 | Global constants | Yes |

---

## Migration Order

### Phase 0: Lock the scope (0.5 day)

1. Freeze a list of pydantic-ai touchpoints (see “Repository Footprint”).
2. Decide the canonical runtime message shape for UI + resume (TinyAgent-native vs our `types/canonical.py`).

### Phase 1: Exceptions (Day 1)

1. Ensure `ToolRetryError` can replace `ModelRetry` behavior (message + any metadata).
2. Replace `ModelRetry` imports in:
   - `core/agents/agent_components/tool_executor.py`
   - `tools/decorators.py`
3. Run tests.

### Phase 2: UI message dispatch (Day 1)

1. Remove `ModelResponse` imports from:
   - `ui/app.py`
   - `ui/headless/output.py`
2. Replace `isinstance` checks with canonical/duck-typed checks.
3. Run tests.

### Phase 3: Serialization + adapters (Day 2)

1. Update `core/state.py` to serialize canonical messages.
2. Update `core/agents/agent_components/message_handler.py` to stop importing `pydantic_ai.messages`.
3. Decide fate of `infrastructure/llm_types.py` (delete or rewrite to TinyAgent).
4. Run tests.

### Phase 4: Loop replacement (Days 3-4)

1. Rewrite `core/agents/main.py` to run TinyAgent instead of pydantic-ai.
2. Map TinyAgent events to existing callbacks:
   - streaming/message updates → `StreamingCallback`
   - tool start/end → `ToolStartCallback` / `ToolResultCallback`
3. Delete DEAD files:
   - `agent_config.py`
   - `streaming.py`, `streaming_debug.py`
   - `response_state.py`, `state_transition.py`
   - `openai_response_validation.py`
4. Run full test suite.

### Phase 5: Cleanup (Day 5)

1. Remove pydantic-ai from `pyproject.toml`.
2. Remove any remaining imports/mentions that are no longer accurate.
3. Run `ruff check --fix .`.
4. Update documentation.

---

## Dependency Graph (conceptual)

```
ui/app.py
  |
  +-> core/agents/main.py (REWRITE)
        |
        +-> agent_components/
        |     +-> agent_config.py (DEAD)
        |     |     +-> openai_response_validation.py (DEAD)
        |     +-> streaming.py (DEAD)
        |     |     +-> streaming_debug.py (DEAD)
        |     +-> response_state.py (DEAD)
        |     |     +-> state_transition.py (DEAD)
        |     +-> orchestrator/
        |           +-> tool_dispatcher.py (REFACTOR/REWIRE)
        |
        +-> resume/ (KEEP)
        +-> core/types/ + types/ (KEEP)
        +-> core/state.py (REFACTOR)
```

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| TinyAgent less battle-tested | We own bugs, can fix quickly |
| Resume/sanitize assumes pydantic-ai message shape | Keep duck typing + add a canonical adapter boundary |
| UI callbacks depend on streaming shape | Define a strict event mapping contract and test it |
| Tool retry semantics differ | Make `ToolRetryError` parity explicit and add tests |
| Hidden pydantic-ai imports inside functions | Use `rg pydantic_ai` as a gate before declaring done |

---

## Effort Estimate (still ~5 days)

| Task | Days |
|------|------|
| Scope lock + exception/type swaps | 1 |
| Serialization + adapters | 1 |
| Loop replacement (main.py) | 2 |
| Testing/cleanup | 1 |
| **Total** | **5** |

---

## Success Criteria

1. All existing tests pass
2. No `pydantic_ai` imports remain anywhere in `src/tunacode/`
3. Streaming works identically from UI perspective
4. Tool execution with retry works
5. Session resume works
