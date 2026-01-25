# Research – TunaCode Architecture Refactoring Status

**Date:** 2026-01-25
**Owner:** Claude (research agent)
**Phase:** Research

## Goal

Assess the current implementation status of the TunaCode architecture refactoring plan and identify what work remains.

## Executive Summary

**Critical Finding:** The refactoring plan in `docs/refactoring/architecture-refactor-plan.md` is **partially implemented but NOT adopted**. Chunks 0-1 (foundational types and adapter layer) are complete, but the codebase hasn't migrated to use them. The canonical types exist but sit unused in production code paths.

| Phase | Chunks | Status |
|-------|--------|--------|
| Phase 1: Foundations | 0-1 | ✅ Complete (types + adapter exist) |
| Phase 2: Parity | 2-4 | 🟡 Partial (tests exist, no migration) |
| Phase 3: Consolidation | 5-8 | ❌ Not started |
| Phase 4: Enforcement | 9-10 | ❌ Not started |

## Chunk-by-Chunk Status

### Chunk 0: Define Target Types — ✅ COMPLETE

**Location:** `src/tunacode/types/canonical.py` (350 lines)

All planned types are implemented:

| Type | Status | Lines |
|------|--------|-------|
| `CanonicalMessage` | ✅ | 89-114 |
| `TextPart`, `ThoughtPart`, `SystemPromptPart` | ✅ | 42-63 |
| `ToolCallPart`, `ToolReturnPart` | ✅ | 66-82 |
| `CanonicalToolCall` | ✅ | 133-158 |
| `ReActScratchpad`, `ReActEntry` | ✅ | 166-204 |
| `TodoItem`, `TodoStatus` | ✅ | 213-248 |
| `UsageMetrics` | ✅ | 257-298 |
| `RecursiveContext` | ✅ | 307-318 |

**Tests:** `tests/unit/types/test_canonical.py` (368 lines) - comprehensive coverage

---

### Chunk 1: Message Adapter Layer — ✅ COMPLETE

**Location:** `src/tunacode/utils/messaging/adapter.py` (315 lines)

All planned functions are implemented:

| Function | Status | Purpose |
|----------|--------|---------|
| `to_canonical()` | ✅ | pydantic-ai → canonical |
| `from_canonical()` | ✅ | canonical → dict for pydantic-ai |
| `get_content()` | ✅ | Replaces polymorphic accessor |
| `get_tool_call_ids()` | ✅ | Extract tool call IDs |
| `get_tool_return_ids()` | ✅ | Extract tool return IDs |
| `find_dangling_tool_calls()` | ✅ | Detect orphaned calls |

**Tests:** `tests/unit/types/test_adapter.py` (355 lines) - includes parity tests

**Key insight:** Adapter handles all 4+ legacy message formats (dict with content, dict with thought, dict with parts, pydantic-ai objects)

---

### Chunk 2: Split SessionState — ❌ NOT STARTED

**Current state:** `SessionState` still has **40+ fields** mixing unrelated concerns

**Evidence from `src/tunacode/core/state.py`:**

```python
@dataclass
class SessionState:
    # 40+ fields including:
    react_scratchpad: dict[str, Any]  # Should be ReActScratchpad
    todos: list[dict[str, Any]]       # Should be list[TodoItem]
    tool_calls: list[dict[str, Any]]  # Should use ToolCallRegistry
    tool_call_args_by_id: dict        # Duplicate tracking
    last_call_usage: dict             # Should be UsageMetrics
    session_total_usage: dict         # Should be UsageMetrics
    # ... many more
```

**Planned sub-structures (NOT created):**
- `ConversationState`
- `ReActState`
- `TaskState`
- `RuntimeState`
- `UsageState`

---

### Chunk 3: Parity Harness for Messages — 🟡 PARTIAL

**What exists:**
- `tests/unit/types/test_adapter.py:258-273` - Parity tests for `get_content()` vs legacy `get_message_content()`
- `tests/unit/types/test_adapter.py:220-255` - Round-trip tests (to_canonical → from_canonical)

**What's missing:**
- `tests/parity/test_message_parity.py` - Full serialization parity against real session files
- Real-world session file validation

---

### Chunk 4: Port Sanitize to Canonical — ❌ NOT STARTED

**Current state:** `src/tunacode/core/agents/resume/sanitize.py` is **631 lines** of polymorphic accessor code

**Evidence:**
- Lines 58-94: Polymorphic accessors (`_get_attr_value`, `_get_message_parts`, `_get_message_tool_calls`)
- Lines 116-178: Tool call ID collection with multiple code paths
- Lines 228-343: Dangling tool call removal with separate dict/object handling

**Planned:** `sanitize_canonical.py` (~100 lines using canonical types) - NOT created

---

### Chunk 5: Tool Call Registry — ❌ NOT STARTED

**Current state:** Tool calls tracked in **THREE separate locations**:

1. `session.tool_calls: list[dict]` - Display metadata (state.py:76)
2. `session.tool_call_args_by_id: dict` - Temporary arg storage (state.py:77)
3. Message parts - Canonical conversation history

**Key files:**
- `core/agents/agent_components/orchestrator/tool_dispatcher.py:70,79,164,289-298` - Record/consume logic
- `core/agents/resume/sanitize.py:262-328` - Must clean all 3 locations

**Planned:** `ToolCallRegistry` class - NOT created (design at plan lines 324-351)

**Types ready:** `CanonicalToolCall` and `ToolCallStatus` exist in `types/canonical.py:133-158`

---

### Chunk 6: Migrate ReAct to Typed Structure — ❌ NOT STARTED

**Current state:**
```python
# state.py:67-69
react_scratchpad: dict[str, Any] = field(default_factory=lambda: {"timeline": []})
react_forced_calls: int = 0
react_guidance: list[str] = field(default_factory=list)
```

**Types ready:** `ReActScratchpad`, `ReActEntry`, `ReActEntryKind` exist in `types/canonical.py:166-204`

---

### Chunk 7: Migrate Todos to Typed Structure — ❌ NOT STARTED

**Current state:**
```python
# state.py:71
todos: list[dict[str, Any]] = field(default_factory=list)
```

**Types ready:** `TodoItem`, `TodoStatus` exist in `types/canonical.py:213-248`

---

### Chunk 8: Usage Tracking Consolidation — ❌ NOT STARTED

**Current state:**
```python
# state.py:88-101
last_call_usage: dict = field(default_factory=lambda: {"prompt_tokens": 0, ...})
session_total_usage: dict = field(default_factory=lambda: {"prompt_tokens": 0, ...})
```

**Types ready:** `UsageMetrics` exists in `types/canonical.py:257-298`

**Also exists but unused:** `TokenUsage`, `CostBreakdown` in `types/dataclasses.py`

---

### Chunk 9: Architecture Tests — ❌ NOT STARTED

**Evidence:** `tests/architecture/` directory does NOT exist

**Planned tests:**
- Import direction enforcement (core cannot import ui)
- SessionState field count limit
- Type contract enforcement

---

### Chunk 10: Delete Legacy Code — ❌ NOT STARTED

**Legacy code still active:**
- `utils/messaging/message_utils.py:6-34` - Legacy `get_message_content()` still called in 3 places:
  - `core/state.py:123`
  - `ui/app.py:352,355`
  - `ui/headless/output.py:50`

---

## Adoption Gap Analysis

**The canonical types exist but are NOT used in production code:**

| Canonical Type | Production Usage |
|----------------|------------------|
| `CanonicalMessage` | Only in adapter.py (3 instantiations) |
| `CanonicalPart` types | Only in adapter.py (10 instantiations) |
| `CanonicalToolCall` | 0 - only in tests |
| `ReActScratchpad` | 0 - only in tests |
| `TodoItem` | 0 - only in tests |
| `UsageMetrics` | 0 - only in tests |
| `RecursiveContext` | 0 - only in tests |

**Root cause:** The adapter layer exists but nothing calls it except tests. The migration from pydantic-ai native types to canonical types hasn't happened.

---

## Knowledge Gaps

1. **Streaming compatibility:** How do frozen dataclasses work with incremental message building during streaming?

2. **Session file backward compatibility:** Adapter handles legacy formats, but has it been tested with real historical session files?

3. **Performance impact:** No benchmarks exist comparing canonical vs polymorphic code paths

4. **Open question from plan:** Need to verify frozen dataclasses don't break pydantic-ai integration

---

## Recommended Next Steps

### Immediate (Low Risk)
1. **Add architecture tests (Chunk 9)** - Can be done in parallel, prevents regression
2. **Migrate legacy accessor calls** - Replace 3 `get_message_content()` calls with `get_content()`
3. **Create parity tests with real sessions** - Validate adapter against production data

### Short-term (Medium Risk)
4. **Port sanitize.py to canonical** - Significant LOC reduction, proves canonical approach works
5. **Migrate TodoItem** - Simple type, low blast radius
6. **Migrate UsageMetrics** - Self-contained, affects only cost tracking

### Medium-term (Higher Risk)
7. **Implement ToolCallRegistry** - Requires coordination across multiple files
8. **Split SessionState** - Breaking change, needs careful shim strategy
9. **Migrate messages to canonical** - Most impactful, requires comprehensive parity testing

---

## References

| File | Purpose |
|------|---------|
| `docs/refactoring/architecture-refactor-plan.md` | Original plan (547 lines) |
| `docs/refactoring/message-flow-map.md` | Message flow documentation |
| `docs/refactoring/dependency-diagram.md` | Dependency visualization |
| `src/tunacode/types/canonical.py` | Target types (350 lines) |
| `src/tunacode/utils/messaging/adapter.py` | Adapter implementation (315 lines) |
| `src/tunacode/core/state.py` | Current SessionState (426 lines) |
| `src/tunacode/core/agents/resume/sanitize.py` | Polymorphic sanitization (631 lines) |
| `tests/unit/types/test_canonical.py` | Canonical type tests (368 lines) |
| `tests/unit/types/test_adapter.py` | Adapter tests (355 lines) |
