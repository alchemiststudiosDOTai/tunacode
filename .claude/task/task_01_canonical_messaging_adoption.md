# Task 01: Canonical Messaging Adoption

## Status: COMPLETE ✓

| Phase | Status | Branch |
|-------|--------|--------|
| P1 (Messaging) | ✓ Complete | `types-architect` |
| P2 (Tooling) | ✓ Complete | `types-architect` |

**Tests:** 430 passed
**LOC delta:** -156 lines in sanitize.py, +5 lines in messaging exports

---

## Summary

Production message handling now uses canonical message and part types. This task was split into two phases:

- **P1 (Messaging):** ✓ Replaced legacy `get_message_content()` with `adapter.get_content()`
- **P2 (Tooling):** ✓ Consolidated tool call tracking by routing sanitize.py through adapter helpers

---

## P1: Message Content Accessor Migration ✓

### Scope

Replace 3 production call sites using legacy `get_message_content()` with the canonical `adapter.get_content()`.

### Changes Made

| File | Change |
|------|--------|
| `src/tunacode/core/state.py` | ✓ Import `get_content` from `messaging`, call in `update_token_count()` |
| `src/tunacode/ui/app.py` | ✓ Import `get_content` from `messaging`, call in `_replay_session_messages()` |
| `src/tunacode/ui/headless/output.py` | ✓ Import `get_content` from `messaging`, call in `_extract_from_messages()` |
| `src/tunacode/utils/messaging/__init__.py` | ✓ Re-exports `get_content` from adapter for convenience |

### Acceptance Criteria - VERIFIED

1. ✓ All 3 call sites use `adapter.get_content()`
2. ✓ No imports from `message_utils` in production code (legacy kept for parity tests)
3. ✓ All existing tests pass (430 tests)
4. ✓ Token counting, session replay, and headless output work correctly

---

## P2: Tool Call Tracking Consolidation ✓

### Scope

Eliminate duplicate tool call tracking logic by routing sanitize.py through canonical adapter helpers.

### Changes Made - sanitize.py

| Function | Status | Notes |
|----------|--------|-------|
| `_get_attr_value()` | ✓ DELETED | Uses `adapter._get_attr()` |
| `_get_message_parts()` | ✓ DELETED | Uses `adapter._get_parts()` |
| `_collect_tool_call_ids_from_parts()` | ✓ DELETED | Detection via adapter |
| `_collect_tool_return_ids_from_parts()` | ✓ DELETED | Detection via adapter |
| `_collect_message_tool_call_ids()` | ✓ DELETED | Detection via adapter |
| `_collect_message_tool_return_ids()` | ✓ DELETED | Detection via adapter |
| `_collect_tool_call_ids_from_tool_calls()` | ✓ DELETED | Detection via adapter |
| `find_dangling_tool_call_ids()` | ✓ THIN WRAPPER | Calls `adapter.find_dangling_tool_calls()` |

### Functions KEPT in sanitize.py

These are mutation/sanitization concerns, not detection:

| Function | Lines | Purpose |
|----------|-------|---------|
| `_set_message_parts()` | 57-64 | Set parts (mutation) |
| `_set_message_tool_calls()` | 66-77 | Set tool_calls (mutation) |
| `_normalize_list()` | 80-89 | Normalize to list (local helper) |
| `_get_message_tool_calls()` | 91-99 | Read tool_calls for mutation |
| `_filter_dangling_tool_calls_from_parts()` | 111-149 | Filter parts (mutation) |
| `_filter_dangling_tool_calls_from_tool_calls()` | 152-178 | Filter tool_calls (mutation) |
| `_strip_dangling_tool_calls_from_message()` | 181-233 | Strip from message (mutation) |
| `remove_dangling_tool_calls()` | 236-280 | Mutate message history |
| `remove_consecutive_requests()` | 283-338 | Repair abort scenarios |
| `remove_empty_responses()` | 341-379 | Repair abort scenarios |
| `_strip_system_prompt_parts()` | 382-392 | Strip system prompts |
| `sanitize_history_for_resume()` | 395-464 | pydantic-ai compatibility |
| `run_cleanup_loop()` | 467-520 | Orchestrate multi-pass cleanup |

### Changes Made - main.py

**BEFORE (35 lines):**
```python
max_cleanup_iterations = 10
total_cleanup_applied = False
for cleanup_iteration in range(max_cleanup_iterations):
    # ... embedded cleanup loop
```

**AFTER (3 lines):**
```python
total_cleanup_applied, dangling_tool_call_ids = run_cleanup_loop(
    session_messages, tool_call_args_by_id
)
```

### Changes Made - messaging/__init__.py

Exports `_get_attr` and `_get_parts` for internal modules (sanitize.py):

```python
from tunacode.utils.messaging.adapter import (
    _get_attr,
    _get_parts,
    find_dangling_tool_calls,
    # ...
)
```

### Acceptance Criteria - VERIFIED

1. ✓ sanitize.py uses adapter functions for detection (`find_dangling_tool_calls`, `_get_attr`, `_get_parts`)
2. ✓ main.py calls `run_cleanup_loop()` instead of embedded loop
3. ✓ Only mutation helpers remain in sanitize.py (detection delegated to adapter)
4. ✓ Resume/abort scenarios work correctly (tests pass)
5. ✓ All existing tests pass (430 tests)

---

## Sequencing - COMPLETE

```
P1 (Messaging) ✓        P2 (Tooling) ✓
     │                       │
     ▼                       │
[Replace 3 call sites] ✓     │
     │                       │
     ▼                       │
[Update __init__.py] ✓       │
     │                       │
     ▼                       ▼
[Tests pass] ✓ ─────► [Route sanitize.py through adapter] ✓
                             │
                             ▼
                     [Replace main.py cleanup loop] ✓
                             │
                             ▼
                     [Tests pass] ✓
```

---

## Files Modified

### P1 Files

- ✓ `src/tunacode/core/state.py` - import/call `get_content`
- ✓ `src/tunacode/ui/app.py` - import/call `get_content`
- ✓ `src/tunacode/ui/headless/output.py` - import/call `get_content`
- ✓ `src/tunacode/utils/messaging/__init__.py` - re-exports `get_content`, `_get_attr`, `_get_parts`

### P2 Files

- ✓ `src/tunacode/core/agents/resume/sanitize.py` - deleted ~156 LOC of duplicate accessors
- ✓ `src/tunacode/core/agents/main.py` - replaced 35-line loop with `run_cleanup_loop()` call
- ✓ `src/tunacode/utils/messaging/adapter.py` - no changes needed (already had helpers)

---

## Related Docs

- [PLAN.md](../../PLAN.md) - Overall architecture refactor plan
- [Architecture Refactor Status](../../memory-bank/research/2026-01-25_architecture-refactor-status.md) - Current implementation status
- [Canonical Types](../../src/tunacode/types/canonical.py) - Target type definitions
- [Message Adapter](../../src/tunacode/utils/messaging/adapter.py) - Canonical adapter implementation
