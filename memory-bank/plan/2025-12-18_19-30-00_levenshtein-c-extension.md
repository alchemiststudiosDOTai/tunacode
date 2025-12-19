---
title: "Levenshtein C Extension – Plan"
phase: Plan
date: "2025-12-18T19:30:00"
owner: "Claude"
parent_research: "memory-bank/research/2025-12-18_update-file-ui-freeze.md"
git_commit_at_plan: "7066c9b"
tags: [plan, performance, ui-freeze, levenshtein]
---

## Goal

- Replace pure-Python Levenshtein with C extension to eliminate 2-10 second UI freezes during `update_file` tool operations.

**Non-goals:**
- Async refactoring of file I/O (separate concern)
- Diff rendering optimization (separate concern)
- Any deployment/observability work

## Scope & Assumptions

**In scope:**
- Add `python-Levenshtein` C extension dependency
- Modify `text_match.py` to use C extension with fallback

**Out of scope:**
- Refactoring `update_file.py` async operations
- Changes to UI rendering pipeline
- Changes to diff generation

**Assumptions:**
- `python-Levenshtein>=0.21.0` is stable and wheels exist for Python 3.11-3.13
- C extension is a direct drop-in (same function signature)
- Fallback to pure Python ensures backwards compatibility if C extension unavailable

## Deliverables

1. Modified `src/tunacode/tools/utils/text_match.py` with C extension integration
2. Updated `pyproject.toml` with new dependency
3. Verified tests pass

## Readiness

- [x] Research document complete
- [x] Target file identified: `src/tunacode/tools/utils/text_match.py:24-51`
- [x] Dependency identified: `python-Levenshtein>=0.21.0`
- [x] Git state clean (7066c9b)

## Milestones

- **M1:** Add dependency to pyproject.toml
- **M2:** Integrate C extension in text_match.py with fallback
- **M3:** Run tests and verify

## Work Breakdown (Tasks)

### T1: Add dependency (M1)

**Summary:** Add `python-Levenshtein>=0.21.0` to pyproject.toml dependencies

**Owner:** Claude

**Dependencies:** None

**Files touched:**
- `pyproject.toml`

**Acceptance test:**
- `uv sync` succeeds and installs python-Levenshtein

---

### T2: Integrate C extension with fallback (M2)

**Summary:** Modify `levenshtein()` function to use C extension when available, keeping pure-Python as fallback

**Owner:** Claude

**Dependencies:** T1

**Files touched:**
- `src/tunacode/tools/utils/text_match.py`

**Implementation:**
```python
# At top of file, after existing imports
try:
    from Levenshtein import distance as _levenshtein_c
    _USE_C_LEVENSHTEIN = True
except ImportError:
    _USE_C_LEVENSHTEIN = False

def levenshtein(a: str, b: str) -> int:
    """Levenshtein distance - uses C extension if available (100x faster)."""
    if _USE_C_LEVENSHTEIN:
        return _levenshtein_c(a, b)

    # Fallback to pure Python
    if not a or not b:
        return max(len(a), len(b))
    # ... existing implementation unchanged
```

**Acceptance test:**
- `from tunacode.tools.utils.text_match import levenshtein; levenshtein("hello", "hallo")` returns `1`

---

### T3: Verify tests pass (M3)

**Summary:** Run test suite to ensure no regressions

**Owner:** Claude

**Dependencies:** T2

**Files touched:** None

**Acceptance test:**
- `uv run pytest` passes

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| C extension missing wheels for some platforms | Low | Medium | Fallback to pure Python implementation |
| API difference in C extension | Very Low | Low | Library is mature, API stable since v0.21 |

## Test Strategy

- Existing tests cover `update_file` functionality
- No new tests required - existing tests validate Levenshtein behavior indirectly
- If tests fail, investigate before proceeding

## References

- Research: `memory-bank/research/2025-12-18_update-file-ui-freeze.md`
- Target file: `src/tunacode/tools/utils/text_match.py:24-51`
- Dependency: https://pypi.org/project/python-Levenshtein/

## Final Gate

- **Plan path:** `memory-bank/plan/2025-12-18_19-30-00_levenshtein-c-extension.md`
- **Milestone count:** 3
- **Task count:** 3
- **Ready for coding:** Yes

**Next command:** `/context-engineer:execute "memory-bank/plan/2025-12-18_19-30-00_levenshtein-c-extension.md"`
