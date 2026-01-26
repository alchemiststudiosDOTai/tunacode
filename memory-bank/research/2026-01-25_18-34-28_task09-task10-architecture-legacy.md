# Research – Task 09 & Task 10: Architecture Enforcement & Legacy Decommission

**Date:** 2026-01-25
**Owner:** Claude (research agent)
**Phase:** Research

## Goal

Investigate requirements for Task 09 (Architecture Enforcement Tests) and Task 10 (Legacy Path Decommission) to establish implementation readiness and identify specific code locations.

## Executive Summary

| Task | Status | Key Finding |
|------|--------|-------------|
| Task 09 | Ready to implement | `tests/architecture/` doesn't exist; 2 dependency violations found |
| Task 10 | Ready to implement | `get_message_content()` has ZERO production usage; safe to delete |

---

## Task 09: Architecture Enforcement Tests

### Current State

**Gap:** No architecture enforcement tests exist. `tests/architecture/` directory is missing.

### Dependency Violations Found

| Location | Import | Violation |
|----------|--------|-----------|
| `src/tunacode/tools/read_file.py:11` | `from tunacode.core.limits import get_max_line_length, get_read_limit` | tools → core |
| `src/tunacode/tools/bash.py:16` | `from tunacode.core.limits import get_command_limit` | tools → core |

**Root Cause:** `core/limits.py` is misplaced. It provides configuration-based limit getters but belongs in `utils/` or `configuration/` layer.

### Clean Dependencies Verified

- `core/` does NOT import from `ui/`
- `tools/` does NOT import from `ui/`
- `utils/` does NOT import from upper layers
- `types/` does NOT import from upper layers

### SessionState Complexity

**Location:** `src/tunacode/core/state.py:45-91`

| Metric | Value | Recommended |
|--------|-------|-------------|
| Total fields | 46 | 20-25 |
| Direct fields | 27 | - |
| Typed sub-structures | 5 | - |
| Nested typed fields | 19 | - |

**Sub-structures created (PR #297):**
- `ConversationState` - 5 fields
- `ReActState` - 1 field (scratchpad)
- `TaskState` - 2 fields
- `RuntimeState` - 9 fields
- `UsageState` - 2 fields

### Tests to Implement

1. **Layer Dependency Direction** (`test_layer_dependencies.py`)
   - Verify: `utils/`, `types/` import nothing from project layers
   - Verify: `tools/` does not import from `core/` or `ui/`
   - Verify: `core/` does not import from `ui/`
   - Exception: `configuration/` and infrastructure (`indexing/`, `lsp/`) are shared

2. **SessionState Field Count Limit** (`test_session_state_complexity.py`)
   - Enforce maximum field count (e.g., 25)
   - Document which fields are decomposed

3. **Import Chain Depth** (`test_import_chains.py`)
   - Detect chains longer than 3 levels

### Implementation Pattern

Auto-discovery pattern from `tests/integration/tools/test_tool_conformance.py:18-54`:
```python
def discover_tools():
    tools_dir = Path(__file__).parent.parent.parent.parent / "src" / "tunacode" / "tools"
    # ... validation logic
```

---

## Task 10: Legacy Path Decommission

### Current State

**Key Finding:** Task 01 (Canonical Messaging Adoption) is COMPLETE. All production code uses canonical adapter functions.

### Legacy Function Ready for Deletion

**File:** `src/tunacode/utils/messaging/message_utils.py:6-34`

- Function: `get_message_content()`
- Production usage: **ZERO**
- Only references: recursive internal calls and test parity checks

### Migration Verification (Complete)

| Call Site | Before | After | Status |
|-----------|--------|-------|--------|
| `core/state.py:99` | `get_message_content(msg)` | `get_content(msg)` | Migrated |
| `ui/app.py:357` | `get_message_content(msg)` | `get_content(msg)` | Migrated |
| `ui/headless/output.py:50` | `get_message_content(msg)` | `get_content(msg)` | Migrated |

### Canonical Adapter Functions (In Production Use)

**File:** `src/tunacode/utils/messaging/adapter.py`

| Function | Lines | Production Call Sites |
|----------|-------|----------------------|
| `get_content()` | 280-293 | state.py, app.py, output.py |
| `get_tool_call_ids()` | 295-300 | sanitize_debug.py:122 |
| `get_tool_return_ids()` | 302-307 | sanitize_debug.py:123 |
| `find_dangling_tool_calls()` | 309-318 | sanitize.py:249 |

### Polymorphic Accessors Deleted

Per `.claude/JOURNAL.md` 2026-01-25 entry (~117 LOC removed):

| Deleted Function | Replacement |
|------------------|-------------|
| `_get_attr_value()` | `adapter._get_attr()` |
| `_get_message_parts()` | `adapter._get_parts()` |
| `_collect_tool_call_ids_from_parts()` | `adapter.get_tool_call_ids()` |
| `_collect_tool_return_ids_from_parts()` | `adapter.get_tool_return_ids()` |
| `_collect_tool_call_ids_from_tool_calls()` | `adapter.get_tool_call_ids()` |

### Mutation Helpers (Keep - By Design)

**File:** `src/tunacode/core/agents/resume/sanitize.py`

These remain because adapter layer is read-only; mutation stays in sanitize.py:

| Function | Lines | Purpose |
|----------|-------|---------|
| `_normalize_list()` | 82-89 | Coerce to list |
| `_get_message_tool_calls()` | 93-96 | Read for mutation (uses `_get_attr()`) |
| `_can_update_tool_calls()` | 99-105 | Mutation check |
| `_replace_message_fields()` | 108-131 | Immutable field replacement |
| `_apply_message_updates()` | 134-156 | Tool call mutation |

### Test Files Requiring Update After Deletion

| File | Line | Update Needed |
|------|------|---------------|
| `tests/unit/core/test_message_utils.py` | 3 | Delete or convert to test `get_content()` |
| `tests/unit/types/test_adapter.py` | 29, 302-314 | Remove parity tests |
| `tests/parity/test_message_parity.py` | 19, 73-75 | Update to only test canonical path |

---

## Recommended Implementation Order

### Immediate (Task 09)

1. Create `tests/architecture/` directory
2. Implement `test_layer_dependencies.py` - prevents regression
3. Implement `test_session_state_complexity.py` - enforces field limits

### Immediate (Task 10)

4. Delete `get_message_content()` from `message_utils.py`
5. Remove export from `utils/messaging/__init__.py:16`
6. Update test files to remove legacy parity checks

### Follow-up

7. Move `core/limits.py` to `utils/limits.py` or `configuration/limits.py`
8. Update imports in `tools/read_file.py:11` and `tools/bash.py:16`

---

## Knowledge Gaps

1. **Field limit threshold:** What's the right max for SessionState? Current: 46, recommended: 20-25
2. **limits.py relocation:** Should it go to `utils/` or `configuration/`?
3. **Test coverage:** No existing architecture tests to model patterns from

---

## References

| File | Purpose |
|------|---------|
| `src/tunacode/core/state.py:45-91` | SessionState definition |
| `src/tunacode/types/state_structures.py` | Typed sub-structures |
| `src/tunacode/utils/messaging/message_utils.py:6-34` | Legacy function to delete |
| `src/tunacode/utils/messaging/adapter.py` | Canonical adapter |
| `src/tunacode/core/agents/resume/sanitize.py` | Mutation helpers |
| `tests/integration/tools/test_tool_conformance.py:18-54` | Auto-discovery pattern |
| `.claude/JOURNAL.md` | Task 01 completion notes |
| `memory-bank/research/2026-01-25_architecture-refactor-status.md` | Prior research |
