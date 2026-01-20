---
title: "Timeout Cleanup Gap – Plan"
phase: Plan
date: "2026-01-19T15:00:00Z"
owner: "claude-agent"
parent_research: "memory-bank/research/2026-01-19_14-30-00_dangling_tool_calls_timeout_gap.md"
git_commit_at_plan: "ed5199ee"
tags: [plan, timeout, cleanup, exception-handling]
---

## Goal

**Fix the timeout-induced dangling tool calls bug by adding `asyncio.CancelledError` to the existing exception handler at `main.py:409`.**

When `GlobalRequestTimeoutError` occurs mid-tool-execution, session messages are left corrupted because `CancelledError` bypasses the cleanup path. This is a one-line fix to an existing exception handler.

**Non-goals:**
- Adding cleanup in `run()` (Option B from research) - duplicates logic
- Belt-and-suspenders approach (Option C) - overkill for this case
- Refactoring exception handling architecture

## Scope & Assumptions

**In Scope:**
- Modify `except UserAbortError:` at `main.py:409` to also catch `asyncio.CancelledError`
- Add ONE test for `CancelledError` cleanup behavior

**Out of Scope:**
- Integration tests for full timeout scenarios (requires complex mocking)
- Changes to `run()` timeout wrapper
- Changes to `GlobalRequestTimeoutError` handling

**Assumptions:**
- Python 3.11+ behavior: `asyncio.wait_for()` raises `CancelledError` inside the inner task before converting to `TimeoutError`
- The cleanup function `_remove_dangling_tool_calls()` is already correct (tested)
- The fix follows the same pattern as the existing `UserAbortError` handling

## Deliverables (DoD)

| Artifact | Acceptance Criteria |
|----------|---------------------|
| `main.py` fix | `except (UserAbortError, asyncio.CancelledError):` at line 409 |
| Test | `test_cancelled_error_triggers_cleanup()` passes |
| Ruff | `ruff check src/tunacode/core/agents/main.py` passes |
| Pytest | `uv run pytest tests/test_tool_call_lifecycle.py -v` passes |

## Readiness (DoR)

- [x] Research document complete
- [x] Code location identified: `src/tunacode/core/agents/main.py:409`
- [x] Cleanup function verified: `_remove_dangling_tool_calls()` at line 486
- [x] Test file exists: `tests/test_tool_call_lifecycle.py`
- [x] No blocking dependencies

## Milestones

| ID | Milestone | Description |
|----|-----------|-------------|
| M1 | Fix | Add `asyncio.CancelledError` to exception handler |
| M2 | Test | Add unit test for CancelledError cleanup |
| M3 | Verify | Run ruff + pytest, ensure green |

## Work Breakdown (Tasks)

### Task 1: Add CancelledError to Exception Handler
**Owner:** executor
**Target:** M1
**Dependencies:** None
**Files:** `src/tunacode/core/agents/main.py`

**Change:**
```python
# Line 409: Change from
except UserAbortError:

# To
except (UserAbortError, asyncio.CancelledError):
```

**Acceptance Tests:**
- [ ] Code compiles
- [ ] `ruff check` passes

### Task 2: Add CancelledError Cleanup Test
**Owner:** executor
**Target:** M2
**Dependencies:** Task 1
**Files:** `tests/test_tool_call_lifecycle.py`

**Test Design:**
```python
def test_cancelled_error_triggers_cleanup():
    """CancelledError should trigger _remove_dangling_tool_calls like UserAbortError."""
    # Arrange: Messages with dangling tool calls
    # Act: Simulate the cleanup that would happen in except block
    # Assert: Dangling tool calls removed, args cleared
```

Note: This tests that the cleanup function works with CancelledError context, not the full exception flow (which requires async mocking).

**Acceptance Tests:**
- [ ] Test passes
- [ ] Test is in hypothesis marker section

### Task 3: Run Verification Suite
**Owner:** executor
**Target:** M3
**Dependencies:** Task 1, Task 2

**Commands:**
```bash
uv run ruff check src/tunacode/core/agents/main.py
uv run pytest tests/test_tool_call_lifecycle.py -v
```

**Acceptance Tests:**
- [ ] All linting passes
- [ ] All tests pass

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| CancelledError has different semantics than UserAbortError | Low | Low | Same cleanup needed regardless; re-raise preserves original exception | Test failure |
| pydantic-ai context manager interferes | Medium | Low | The cleanup happens AFTER context manager exits | Manual testing |

## Test Strategy

**ONE test only:** `test_cancelled_error_triggers_cleanup()`

This test verifies that the same cleanup logic that works for `UserAbortError` also works when invoked from `CancelledError` context. The existing property-based tests for `_remove_dangling_tool_calls()` already cover the cleanup function itself.

## References

- Research: `memory-bank/research/2026-01-19_14-30-00_dangling_tool_calls_timeout_gap.md`
- Original fix: PR #246 (dangling tool calls on UserAbortError)
- Delta card: `.claude/delta/2026-01-17-dangling-tool-calls.md`
- Gate 6: Exception paths are first-class (CLAUDE.md)

---

## Next Step

Execute this plan:
```
/context-engineer:execute "memory-bank/plan/2026-01-19_15-00-00_timeout_cleanup_gap.md"
```
