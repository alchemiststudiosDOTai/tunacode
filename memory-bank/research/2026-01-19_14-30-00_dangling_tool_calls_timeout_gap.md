# Research - Dangling Tool Calls Bug: Timeout Gap

**Date:** 2026-01-19
**Owner:** claude-agent
**Phase:** Research

## Goal

Investigate whether the dangling tool calls fix (PR #246) covers timeout scenarios (`GlobalRequestTimeoutError`), or if timeout-induced cancellation can leave the same corrupted message state.

## Findings

### Current Fix (PR #246)

The `UserAbortError` path is properly handled at `src/tunacode/core/agents/main.py:409-417`:

```python
except UserAbortError:
    # Clean up dangling tool calls to prevent API errors on next request
    cleanup_applied = _remove_dangling_tool_calls(
        self.state_manager.session.messages,
        self.state_manager.session.tool_call_args_by_id,
    )
    if cleanup_applied:
        self.state_manager.session.update_token_count()
    raise
```

### The Gap: Timeout Does NOT Trigger Cleanup

The timeout wrapping at `src/tunacode/core/agents/main.py:309-322`:

```python
async def run(self) -> AgentRun:
    timeout = _coerce_global_request_timeout(self.state_manager)
    if timeout is None:
        return await self._run_impl()

    try:
        return await asyncio.wait_for(self._run_impl(), timeout=timeout)
    except TimeoutError as e:
        raise GlobalRequestTimeoutError(timeout) from e  # NO CLEANUP!
```

**When timeout occurs:**
1. `asyncio.wait_for()` cancels `_run_impl()` via `asyncio.CancelledError`
2. `CancelledError` is NOT caught by `except UserAbortError` at line 409
3. `CancelledError` propagates up (or is suppressed by wait_for)
4. `TimeoutError` is caught at line 321
5. `GlobalRequestTimeoutError` is raised WITHOUT calling `_remove_dangling_tool_calls()`
6. **Session messages left with dangling tool calls**

### Relevant Files

| File | Why It Matters |
|------|----------------|
| `src/tunacode/core/agents/main.py:309-322` | Timeout wrapper - missing cleanup |
| `src/tunacode/core/agents/main.py:409-417` | UserAbort cleanup - works correctly |
| `src/tunacode/core/agents/main.py:486-508` | `_remove_dangling_tool_calls()` function |
| `src/tunacode/exceptions.py:268-278` | `GlobalRequestTimeoutError` definition |
| `.claude/delta/2026-01-17-dangling-tool-calls.md` | Original bug documentation |

## Key Patterns / Solutions Found

### Pattern: Exception Path Asymmetry

The code has asymmetric exception handling:
- `UserAbortError` → cleanup + re-raise
- `GlobalRequestTimeoutError` → convert + re-raise (no cleanup)
- `asyncio.CancelledError` → not caught at all

### Pattern: Two-Layer Exception Handling

The timeout triggers at the **outer** layer (`run()`), but cleanup only happens in the **inner** layer (`_run_impl()`):

```
run() → try/except TimeoutError → GlobalRequestTimeoutError (no cleanup)
    └── _run_impl() → try/except UserAbortError → cleanup (works)
```

### Solution Options

**Option A: Catch CancelledError in _run_impl() (Recommended)**

```python
# main.py:409
except (UserAbortError, asyncio.CancelledError):
    cleanup_applied = _remove_dangling_tool_calls(...)
    if cleanup_applied:
        self.state_manager.session.update_token_count()
    raise
```

**Pros:**
- Single cleanup location
- Handles both abort and timeout cancellation
- Consistent with Gate 6 (exception paths are first-class)

**Cons:**
- `CancelledError` isn't semantically an "abort" - but it has same state cleanup needs

**Option B: Add cleanup in run() before raising GlobalRequestTimeoutError**

```python
# main.py:321
except TimeoutError as e:
    cleanup_applied = _remove_dangling_tool_calls(
        self.state_manager.session.messages,
        self.state_manager.session.tool_call_args_by_id,
    )
    if cleanup_applied:
        self.state_manager.session.update_token_count()
    raise GlobalRequestTimeoutError(timeout) from e
```

**Pros:**
- Explicit cleanup for timeout path
- Doesn't conflate abort with cancellation

**Cons:**
- Duplicates cleanup logic
- `self.state_manager` isn't in scope - needs refactoring

**Option C: Both Options A and B**

Both layers handle their respective exceptions:
- `_run_impl()` catches `CancelledError` from any source (defensive)
- `run()` catches `TimeoutError` as backup (belt-and-suspenders)

This is safest but may be overkill.

## Knowledge Gaps

### Uncertain: CancelledError Propagation

When `asyncio.wait_for()` times out:
1. It calls `task.cancel()` on the inner task
2. This raises `CancelledError` inside `_run_impl()`
3. If uncaught, does it propagate to `run()`?
4. Does `wait_for` convert it to `TimeoutError` automatically?

**Python 3.11+ Behavior:** `wait_for()` should suppress the `CancelledError` and raise `TimeoutError` instead. But the inner task's state is still potentially dirty.

### Missing: Test Coverage

No tests exist for:
- `GlobalRequestTimeoutError` during tool execution
- Message state after timeout
- `CancelledError` handling in `_run_impl()`

### Unknown: pydantic-ai Context Manager

The `async with agent.iter()` at line 349 is a pydantic-ai context manager. Unknown if:
- It has cleanup on `CancelledError`
- It commits partial messages to some internal state
- It affects the `message_history` we passed in

## References

### Codebase Files
- `src/tunacode/core/agents/main.py` - Main agent orchestration
- `src/tunacode/exceptions.py` - Exception definitions
- `.claude/delta/2026-01-17-dangling-tool-calls.md` - Original bug fix documentation
- `tests/test_tool_call_lifecycle.py` - Existing cleanup tests (unit level only)

### Related Documentation
- `docs/codebase-map/architecture/conversation-turns.md` - Message invariants
- `CLAUDE.md` Gate 6 - Exception paths are first-class

## Recommended Next Steps

1. **Immediate Fix**: Add `asyncio.CancelledError` to the except clause at line 409
2. **Test Coverage**: Add tests for timeout mid-tool-call scenario
3. **Documentation**: Update delta card to note timeout was not originally covered
4. **Verification**: Manually test timeout during tool execution to confirm bug exists

## Visual Summary

```
BEFORE FIX (Current State)
==========================
Timeout during tool execution:
  ModelResponse(tool_calls=[A, B])
  → execute tool A
  → asyncio.wait_for timeout triggers
  → CancelledError raised (NOT caught)
  → TimeoutError caught in run()
  → GlobalRequestTimeoutError raised
  → messages still has ModelResponse with [A, B]
  → NO ToolReturn recorded
  → Next request fails!

AFTER FIX (Proposed)
====================
Timeout during tool execution:
  ModelResponse(tool_calls=[A, B])
  → execute tool A
  → asyncio.wait_for timeout triggers
  → CancelledError raised
  → CancelledError caught in _run_impl() ← NEW
  → _remove_dangling_tool_calls() called ← NEW
  → CancelledError re-raised
  → TimeoutError caught in run()
  → GlobalRequestTimeoutError raised
  → messages cleaned (no dangling calls)
  → Next request works!
```
