# Research – Unprocessed Tool Calls Issue Map

**Date:** 2026-01-21
**Owner:** Claude Agent
**Phase:** Research

## Goal

Map the full evolution of the "unprocessed/dangling tool calls" bug from initial discovery through multiple PRs and fixes, documenting root causes, solutions, and the current architecture.

## Timeline of Issues

### Phase 1: Initial Bug Discovery (PR #246, 2026-01-17)

**Symptom:** After user abort (Ctrl+C/ESC) mid-tool-call, the next API request fails.

**Root Cause:** Message invariant violation.
- Every `ModelResponse` with `tool_calls` MUST be followed by matching `ToolReturn(s)`
- User abort broke out of loop BEFORE recording tool returns
- API rejected next request due to pending unanswered tool calls

**Fix:** Added `_remove_dangling_tool_calls()` in `except UserAbortError` handler.

**Files:**
- `src/tunacode/core/agents/main.py` - Initial cleanup implementation
- `.claude/delta/2026-01-17-dangling-tool-calls.md` - Bug documentation

**Commit:** `385da635` (PR #246: arrow-cleanup)

---

### Phase 2: Non-Trailing Dangling Calls (2026-01-21 Investigation)

**Symptom:** Requests hang even after cleanup. Timeout after 120s.

**Root Cause:** Original cleanup only removed TRAILING dangling tool calls.
```python
# Original logic (simplified)
while messages:
    last_message = messages[-1]
    if not has_tool_calls(last_message):
        break  # <-- STOPS if user message is last!
    # ... remove
```

If user sends a new message AFTER abort, the dangling tool calls are buried in the middle of history, not at the end.

**Sequence:**
1. Model makes 3 tool calls (`msg[-3]`: response with tool-call parts)
2. User hits ESC during tool execution
3. No `tool-return` messages added
4. User sends new message (`msg[-1]`)
5. Session saved with dangling calls hidden in middle

**Solution:** Scan ENTIRE message history for tool calls without returns, not just trailing.

**Files:**
- `.claude/debug_history/2026-01-21_abort-hang-investigation.md`

---

### Phase 3: Empty Responses & Consecutive Requests (PR #257, 2026-01-20)

**Symptoms found during investigation:**

1. **Empty Response Messages** (`kind=response parts=0`)
   - Occurs when abort during response generation before any content
   - API can't handle empty responses in sequence

2. **Consecutive Request Messages** (multiple `kind=request` in a row)
   - Occurs when abort before model responds, then user sends new message
   - API expects alternating request/response pattern

3. **CancelledError Not Caught** (Python 3.8+)
   - `except Exception` does NOT catch `asyncio.CancelledError`
   - `CancelledError` inherits from `BaseException`
   - Stream cleanup code was bypassed on abort

**Solution:** Three new cleanup functions:
- `remove_empty_responses()` - removes `kind=response parts=0`
- `remove_consecutive_requests()` - keeps only last request in runs
- Added `except asyncio.CancelledError` handler

**Commit:** `ad53e0b4` - fix: resolve session resume hangs after user abort

---

### Phase 4: System Prompt Duplication (2026-01-21)

**Symptom:** Stream opens but receives 0 events. Provider hangs.

**Root Cause:** pydantic-ai v1.21.0+ automatically injects system prompts via `agent.iter()`.
- When `message_history` from previous session contains `system-prompt` parts
- Model receives **duplicate** system prompts (old + fresh)
- Causes models to hang or behave unpredictably

**Solution:** Added `_strip_system_prompt_parts()` to remove system prompts from history before resume.

**Files:**
- `.claude/JOURNAL.md` - Entry "2026-01-21: pydantic-ai System Prompt Stripping Fix"

---

### Phase 5: Resume Module Refactor (PR #272, 2026-01-21)

**Task:** Extract all cleanup logic into dedicated `resume/` module.

**Architecture:**
```
src/tunacode/core/agents/
├── resume/
│   ├── __init__.py      # Public API (9 exports)
│   ├── sanitize.py      # 7 cleanup functions (672 lines)
│   ├── prune.py         # Tool output pruning (179 lines)
│   ├── summary.py       # Rolling summary generation (203 lines)
│   └── filter.py        # History truncation (61 lines)
└── main.py              # Reduced from ~1312 to ~740 lines
```

**Commit:** `b2e050b0` (PR #272)

---

## Current Architecture

### Key Files

| File | Purpose |
|------|---------|
| `src/tunacode/core/agents/resume/sanitize.py` | Core cleanup functions |
| `src/tunacode/core/agents/resume/__init__.py` | Public API exports |
| `src/tunacode/core/agents/main.py:368-424` | Cleanup invocation |
| `tests/integration/core/test_tool_call_lifecycle.py` | Test coverage |

### Cleanup Functions (sanitize.py)

| Function | Line | Purpose |
|----------|------|---------|
| `find_dangling_tool_call_ids()` | 185 | Detect tool calls without returns |
| `remove_dangling_tool_calls()` | 311 | Remove dangling calls + clear cached args |
| `remove_empty_responses()` | 411 | Remove response messages with 0 parts |
| `remove_consecutive_requests()` | 353 | Keep only last request in runs |
| `sanitize_history_for_resume()` | 465 | Strip system prompts, clear run_id |
| `run_cleanup_loop()` | 537 | Orchestrator - runs until stable |

### Cleanup Order (Critical!)

```
1. Dangling Tool Calls → May create empty responses
2. Empty Responses    → May expose consecutive requests
3. Consecutive Requests → May orphan tool returns (new dangling)
4. Loop until stable (max 10 iterations)
```

**Why iterative:** Each cleanup can expose issues for subsequent cleanups.

### Message Invariants

1. **Tool Call Pairing:** Every `ModelResponse` with `tool_calls` MUST be followed by matching `ToolReturn(s)` before next `ModelRequest`

2. **No Empty Responses:** `kind=response` messages must have at least one part

3. **Alternating Pattern:** Request → Response → Request → Response...

4. **No Duplicate System Prompts:** pydantic-ai injects fresh system prompt; history must not contain stale ones

---

## Related PRs & Issues

### PRs
| PR | Title | Status |
|----|-------|--------|
| #246 | chore: arrow-cleanup - tool call handling | MERGED |
| #257 | fix: persist messages on abort | MERGED |
| #272 | feat: extract session resume logic into dedicated resume/ module | MERGED |

### Issues
| Issue | Title | Status |
|-------|-------|--------|
| #258 | bug: new prompt fails if history ends with unprocessed tool calls | OPEN |
| #259 | Tech Debt: test_tool_call_lifecycle.py exceeds 600 line limit | OPEN |
| #260 | Document: Tool lifecycle - don't break agent loop | CLOSED |
| #269 | refactor: modularize abort recovery fixes | CLOSED |

---

## Key Commits

```
385da635 - chore: arrow-cleanup - tool call handling, debug diagnostics, and panel width fixes (#246)
ad53e0b4 - fix: resolve session resume hangs after user abort
587ab234 - fix: persist messages on abort (#257)
9c24e66a - debug: add tracing to dangling tool call detection
6634bbdd - debug: add [PRUNED] tag when dangling tool calls are removed
4f300e30 - refactor: extract session resume logic into dedicated resume/ module
b2e050b0 - feat: extract session resume logic into dedicated resume/ module (#272)
```

---

## Key Patterns / Solutions Found

| Pattern | Description |
|---------|-------------|
| **Reverse iteration for deletion** | `for idx in reversed(indices_to_remove)` prevents index shifting |
| **Dual storage handling** | pydantic-ai stores tool calls in `parts` AND `tool_calls` metadata |
| **Iterative cleanup** | Single pass insufficient; cleanup can create new issues |
| **BaseException for CancelledError** | Python 3.8+: `CancelledError` inherits from `BaseException`, not `Exception` |
| **In-place mutation** | `messages[:] = remaining_messages` preserves caller's reference |

---

## Knowledge Gaps

1. **Issue #258 still open** - "new prompt fails if history ends with unprocessed tool calls" - may need additional edge case handling

2. **Provider-specific behavior** - Chutes/Devstral hangs on tool call history (documented in `.claude/debug_history/2026-01-21_resume-hang-investigation-updated.md`)

3. **Rolling summary integration** - `summary.py` and `filter.py` created but not yet wired into request loop (Issue #271)

---

## References

### Documentation
- `.claude/delta/2026-01-17-dangling-tool-calls.md` - Original bug delta
- `.claude/debug_history/2026-01-21_abort-hang-investigation.md` - Non-trailing investigation
- `.claude/debug_history/2026-01-21_resume-hang-investigation.md` - Resume hang investigation
- `.claude/debug_history/2026-01-21_resume-hang-investigation-updated.md` - Provider issue discovery
- `.claude/debug_history/2026-01-21_stream-hang-timeout.md` - Stream timeout investigation
- `.claude/JOURNAL.md` - Session resume hang fix + resume module refactor entries

### Code
- `src/tunacode/core/agents/resume/sanitize.py` - Cleanup implementations
- `src/tunacode/core/agents/main.py:368-424` - Cleanup invocation
- `tests/integration/core/test_tool_call_lifecycle.py:555-694` - Test coverage

### CLAUDE.md Lessons
```
[2026-01-17] [bug] **Dangling tool calls on user abort (PR #246).**
User aborts mid-tool-call → `messages` has `ModelResponse` with tool calls
but no `ToolReturn` → next API request fails. Root cause: exception path
violated message invariant. Fix: `_remove_dangling_tool_calls()` in
`except UserAbortError`. Prevention: Document state invariants.
Test exception scenarios. See Gate 6.
```

---

## Prevention Guidelines (Gate 6)

Before writing a stateful loop:
1. **What exceptions can exit this loop?** List them all
2. **For each exception: what state is left behind?** Trace the mutation
3. **For each exception: is that state valid for the next operation?** If no, add cleanup
4. **Do tests exist for exception scenarios?** If no, write them

Exception paths are first-class citizens. Every path out of a stateful operation must leave state valid.
