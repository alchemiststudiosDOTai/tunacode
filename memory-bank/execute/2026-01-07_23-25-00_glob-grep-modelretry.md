---
title: "Glob/Grep ModelRetry Fix – Execution Log"
phase: Execute
date: "2026-01-07_23-25-00"
owner: "claude"
plan_path: "memory-bank/plan/2026-01-07_23-12-56_glob-grep-modelretry.md"
start_commit: "17e2573"
end_commit: "6a24f38"
rollback_commit: "17e2573"
status: "SUCCESS"
env: {target: "local", notes: "TDD approach - tests first"}
---

## Pre-Flight Checks

- [x] DoR satisfied? Yes - plan document complete with all 4 tasks
- [x] Access/secrets present? N/A - no external services
- [x] Fixtures/data ready? N/A - tests use tmp_path
- [x] Reference implementation verified? Yes - `list_dir.py:182-186`

## Execution Progress

### Task T1 – Write failing tests
- **Status:** COMPLETED
- **Files touched:**
  - `tests/test_glob_grep_path_validation.py` (new)

**Commands:**
```bash
uv run pytest tests/test_glob_grep_path_validation.py -v
# Result: 4 failed (expected - TDD)
```

**Notes:**
- Created 4 test cases following `tests/test_tool_retry.py` patterns
- Tests expect `ModelRetry` to be raised on bad paths
- All 4 tests failed initially (correct TDD behavior)

---

### Task T2 – Fix glob.py path validation
- **Status:** COMPLETED
- **Files touched:**
  - `src/tunacode/tools/glob.py`

**Changes:**
1. Added `from pydantic_ai.exceptions import ModelRetry` import
2. Changed lines 77-80: replaced `return f"Error: ..."` with `raise ModelRetry(...)`

**Commands:**
```bash
uv run pytest tests/test_glob_grep_path_validation.py -k glob -v
# Result: 2 passed
```

---

### Task T3 – Fix grep.py path validation
- **Status:** COMPLETED
- **Files touched:**
  - `src/tunacode/tools/grep.py`

**Changes:**
1. Added `from pydantic_ai.exceptions import ModelRetry` import
2. Added directory validation at lines 100-105 (before fast_glob call)
3. Added `except ModelRetry: raise` at line 203-205 to prevent wrapping in ToolExecutionError

**Commands:**
```bash
uv run pytest tests/test_glob_grep_path_validation.py -k grep -v
# Result: 2 passed (after adding ModelRetry exception passthrough)
```

**Notes:**
- Initial attempt failed because ModelRetry was caught by generic `except Exception` and wrapped in ToolExecutionError
- Fix: Added explicit `except ModelRetry: raise` before the generic handler

---

### Task T4 – Full test suite verification
- **Status:** COMPLETED

**Commands:**
```bash
uv run pytest
# Result: 192 passed in 17.96s

uv run ruff check src/tunacode/tools/glob.py src/tunacode/tools/grep.py tests/test_glob_grep_path_validation.py
# Result: All checks passed!
```

---

## Gate Results

- **Gate C (Pre-merge):** PASSED
  - Tests: 192 passed
  - Linting: All checks passed (ruff)
  - Type checks: N/A (not enforced)

## Summary

**Files changed:**
1. `src/tunacode/tools/glob.py` - Added ModelRetry import, replaced error string returns with raises
2. `src/tunacode/tools/grep.py` - Added ModelRetry import, added directory validation, added exception passthrough
3. `tests/test_glob_grep_path_validation.py` - New test file with 4 test cases

**Behavior change:**
- `glob` and `grep` now raise `ModelRetry` on invalid paths instead of returning error strings
- This enables LLM self-correction when paths are wrong
- Consistent with `list_dir` implementation pattern

## Follow-ups

- None identified

## References

- Plan: `memory-bank/plan/2026-01-07_23-12-56_glob-grep-modelretry.md`
- Research: `memory-bank/research/2026-01-07_23-10-22_glob-grep-error-strings.md`
- Reference impl: `src/tunacode/tools/list_dir.py:182-186`
