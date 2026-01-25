# Task 02: SessionState Decomposition

## Status: PENDING

| Phase | Status | Branch |
|-------|--------|--------|
| P1 (Analysis) | ○ Pending | - |
| P2 (Decomposition) | ○ Pending | - |

**Depends on:** Task 01 ✓ (canonical messaging adopted)

---

## Summary

`SessionState` remains a single, large structure with mixed concerns and unclear ownership boundaries. The current shape makes it hard to reason about state responsibilities and amplifies coupling across unrelated domains.

**Goal:** Decompose `SessionState` into focused sub-structures with clear ownership.

---

## Context

`src/tunacode/core/state.py` contains 40+ fields including:
- ReAct scratchpad data (`react_scratchpad`, `react_forced_calls`, `react_guidance`)
- Todos (`todos`)
- Tool call tracking (`tool_calls`, `tool_call_args_by_id`)
- Usage metrics (`last_call_usage`, `session_total_usage`)
- Messages (`messages`)
- Agent cache (`agents`, `agent_versions`)
- Runtime state (`current_iteration`, `iteration_count`, `request_id`)

Planned sub-structures from PLAN.md:
- `ConversationState` - messages, token counts
- `ReActState` - scratchpad, guidance, forced calls
- `TaskState` - todos, original query
- `RuntimeState` - iteration tracking, request ID
- `UsageState` - metrics, cost breakdown

---

## Lessons from Task 01

Task 01 (canonical messaging adoption) established patterns to follow:

### 1. Adapter Pattern Works
The `messaging/adapter.py` successfully handles polymorphism between dict and pydantic-ai messages. This same pattern can be applied to state access:
- Create typed accessors for each sub-state
- Hide internal structure from consumers

### 2. Detection vs Mutation Separation
Task 01 separated:
- **Detection** → routed through adapter (read-only)
- **Mutation** → kept in sanitize.py (write operations)

Apply same pattern to state:
- **Reading state** → typed accessors with validation
- **Mutating state** → explicit setters with invariant checks

### 3. Incremental Migration
Task 01 migrated 3 call sites first, then consolidated sanitize.py. Same approach:
- P1: Create sub-structures and typed accessors
- P2: Migrate consumers incrementally

### 4. LOC Reduction is a Feature
Task 01 deleted ~156 LOC of duplicate accessors. Decomposition should similarly:
- Eliminate scattered field access
- Centralize state invariants
- Remove ad-hoc state manipulation

---

## P1: Analysis & Sub-Structure Design

### Scope

Analyze current `SessionState` usage and design typed sub-structures.

### Tasks

| Task | Status | Notes |
|------|--------|-------|
| Grep all `session.` field access patterns | ○ Pending | Identify coupling |
| Categorize fields by domain | ○ Pending | Conversation, ReAct, Task, Runtime, Usage |
| Design `ConversationState` dataclass | ○ Pending | messages, token_count |
| Design `ReActState` dataclass | ○ Pending | scratchpad, guidance, forced_calls |
| Design `TaskState` dataclass | ○ Pending | todos, original_query |
| Design `RuntimeState` dataclass | ○ Pending | iteration, request_id |
| Design `UsageState` dataclass | ○ Pending | metrics, costs |
| Define ownership boundaries | ○ Pending | Who can mutate what |

### Acceptance Criteria

1. All 40+ fields categorized into sub-structures
2. Each sub-structure has clear single responsibility
3. Ownership boundaries documented
4. Migration path identified for each consumer

---

## P2: Decomposition Implementation

### Scope

Implement sub-structures and migrate consumers.

### Tasks

| Task | Status | Notes |
|------|--------|-------|
| Create typed sub-structure dataclasses | ○ Pending | In `types/canonical.py` or new module |
| Add sub-structures to `SessionState` | ○ Pending | Nested composition |
| Create typed accessors | ○ Pending | Following adapter pattern |
| Migrate `main.py` state access | ○ Pending | ReAct, iteration tracking |
| Migrate `state.py` internal methods | ○ Pending | Token counting, persistence |
| Migrate `sanitize.py` state access | ○ Pending | Tool call tracking |
| Update tests | ○ Pending | Verify state isolation |
| Remove deprecated direct field access | ○ Pending | After migration complete |

### Acceptance Criteria

1. `SessionState` uses typed sub-structures
2. All consumers use typed accessors (no direct `session.field` for internal state)
3. Sub-structures have clear invariants enforced
4. Tests pass (430+)
5. No regression in session persistence/resume

---

## Files to Modify

### New Files
- `src/tunacode/types/state_structures.py` - Sub-structure definitions (or extend `canonical.py`)

### Modified Files
- `src/tunacode/core/state.py` - Decompose `SessionState`, add accessors
- `src/tunacode/core/agents/main.py` - Use typed accessors for ReAct, iteration
- `src/tunacode/core/agents/resume/sanitize.py` - Use typed accessors for tool tracking
- `src/tunacode/ui/app.py` - Use typed accessors for session state

---

## Related Docs

- [PLAN.md](../../PLAN.md) - Overall architecture refactor plan
- [Task 01](./task_01_canonical_messaging_adoption.md) - Canonical messaging (COMPLETE)
- [Architecture Refactor Status](../../memory-bank/research/2026-01-25_architecture-refactor-status.md)
- [Canonical Types](../../src/tunacode/types/canonical.py) - Existing type definitions
