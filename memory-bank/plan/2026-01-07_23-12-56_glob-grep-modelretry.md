---
title: "Glob/Grep ModelRetry Fix – Plan"
phase: Plan
date: "2026-01-07_23-12-56"
owner: "claude"
parent_research: "memory-bank/research/2026-01-07_23-10-22_glob-grep-error-strings.md"
git_commit_at_plan: "a891c71"
tags: [plan, tools, error-handling, modelretry]
---

## Goal

- Fix `glob` and `grep` tools to raise `ModelRetry` instead of returning error strings for recoverable path errors, enabling LLM self-correction.

**Non-goals:**
- Changing tool return formats for valid operations
- Adding observability/logging infrastructure
- Modifying the retry mechanism itself

## Scope & Assumptions

**In scope:**
- `src/tunacode/tools/glob.py` - directory validation
- `src/tunacode/tools/grep.py` - add directory validation
- `tests/test_glob_grep_path_validation.py` - new test file

**Out of scope:**
- Other tools (already using correct pattern)
- Retry mechanism changes
- Tool executor modifications

**Assumptions:**
- `pydantic_ai.exceptions.ModelRetry` import available (used elsewhere)
- Test pattern follows `tests/test_tool_retry.py` structure

## Deliverables

1. Fixed `glob.py` with `ModelRetry` raises
2. Fixed `grep.py` with directory validation + `ModelRetry` raises
3. Test file validating both tools raise `ModelRetry` on bad paths

## Readiness

- [x] Research document complete
- [x] Reference implementation verified (`list_dir.py`)
- [x] Affected lines confirmed (glob:74-78, grep:102-113)
- [x] No existing tests to break

## Milestones

- **M1**: Write failing tests (TDD approach per user request)
- **M2**: Fix glob.py
- **M3**: Fix grep.py
- **M4**: Verify all tests pass

## Work Breakdown (Tasks)

### Task 1: Write failing tests
**ID:** T1
**Summary:** Create `tests/test_glob_grep_path_validation.py` with tests that expect `ModelRetry` on bad paths
**Owner:** claude
**Dependencies:** None
**Milestone:** M1
**Files touched:**
- `tests/test_glob_grep_path_validation.py` (new)

**Acceptance test:** Tests exist and FAIL when run (proving they're testing the right thing)

**Test cases to implement:**
```python
# Test 1: glob with nonexistent directory raises ModelRetry
# Test 2: glob with file path (not directory) raises ModelRetry
# Test 3: grep with nonexistent directory raises ModelRetry
# Test 4: grep with file path (not directory) raises ModelRetry
```

---

### Task 2: Fix glob.py path validation
**ID:** T2
**Summary:** Replace error string returns with `ModelRetry` raises in glob.py lines 74-78
**Owner:** claude
**Dependencies:** T1
**Milestone:** M2
**Files touched:**
- `src/tunacode/tools/glob.py`

**Change:**
```python
# Line 74-78: Replace return statements with raises
# Before:
return f"Error: Directory '{directory}' does not exist"
return f"Error: '{directory}' is not a directory"

# After:
raise ModelRetry(f"Directory not found: {directory}. Check the path.")
raise ModelRetry(f"Not a directory: {directory}. Provide a directory path.")
```

**Acceptance test:** `pytest tests/test_glob_grep_path_validation.py -k glob` passes

---

### Task 3: Fix grep.py path validation
**ID:** T3
**Summary:** Add directory validation before `fast_glob` call in grep.py, raising `ModelRetry` for bad paths
**Owner:** claude
**Dependencies:** T1
**Milestone:** M3
**Files touched:**
- `src/tunacode/tools/grep.py`

**Change:**
```python
# Add after line 100, before fast_glob call:
dir_path = Path(directory).resolve()
if not dir_path.exists():
    raise ModelRetry(f"Directory not found: {directory}. Check the path.")
if not dir_path.is_dir():
    raise ModelRetry(f"Not a directory: {directory}. Provide a directory path.")
```

**Acceptance test:** `pytest tests/test_glob_grep_path_validation.py -k grep` passes

---

### Task 4: Full test suite verification
**ID:** T4
**Summary:** Run full test suite to ensure no regressions
**Owner:** claude
**Dependencies:** T2, T3
**Milestone:** M4
**Files touched:** None

**Acceptance test:** `uv run pytest` passes with no failures

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `ModelRetry` import path different | Verify in existing code first |
| grep's `fast_glob` handles paths differently | Test explicitly |
| Tests import tool incorrectly | Follow existing test patterns |

## Test Strategy

- **TDD approach:** Write tests FIRST (Task 1), verify they fail, then implement fixes
- 4 test cases total: 2 for glob, 2 for grep
- Each test verifies `ModelRetry` is raised with appropriate message

## References

- Research: `memory-bank/research/2026-01-07_23-10-22_glob-grep-error-strings.md`
- Reference impl: `src/tunacode/tools/list_dir.py:182-186`
- Existing tests: `tests/test_tool_retry.py`

## Final Gate

- **Plan path:** `memory-bank/plan/2026-01-07_23-12-56_glob-grep-modelretry.md`
- **Milestones:** 4
- **Tasks ready for coding:** 4

**Next command:** `/context-engineer:execute memory-bank/plan/2026-01-07_23-12-56_glob-grep-modelretry.md`
