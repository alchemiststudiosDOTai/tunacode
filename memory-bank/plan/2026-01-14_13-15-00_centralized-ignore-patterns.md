---
title: "Centralized Ignore Patterns - Plan"
phase: Plan
date: "2026-01-14T13:15:00"
owner: "Claude"
parent_research: "memory-bank/research/2026-01-14_12-50-37_centralized-ignore-patterns.md"
git_commit_at_plan: "745a56b"
tags: [plan, ignore-patterns, tools, coding]
---

## Goal

Create a centralized `IgnoreManager` class in `src/tunacode/tools/ignore.py` that provides gitignore-aware file filtering for all discovery tools (glob, list_dir, grep), eliminating duplication and enabling actual .gitignore file parsing via pathspec.

### Non-Goals

- Modifying direct access tools (read_file, write_file, update_file)
- Adding CLI flags (--no-ignore) - deferred to Phase 4
- Performance benchmarking pathspec vs fnmatch
- Nested .gitignore handling in subdirectories (complexity deferred)

## Scope & Assumptions

### In Scope

- New `src/tunacode/tools/ignore.py` module with `IgnoreManager` class
- Integration into glob.py, list_dir.py, grep_components/file_filter.py
- Consolidation of `indexing/constants.py` IGNORE_DIRS duplicate
- Root-level .gitignore parsing via pathspec

### Out of Scope

- Nested .gitignore in subdirectories (future enhancement)
- Override flags for bypassing ignore
- Performance optimization beyond current baseline

### Assumptions

- pathspec 0.12.1 already installed (verified)
- Existing DEFAULT_EXCLUDE_DIRS fast-path optimization retained
- Tools are async but ignore checking is synchronous (no I/O during match)

## Deliverables

1. `src/tunacode/tools/ignore.py` - IgnoreManager class with:
   - `should_ignore(path: Path) -> bool`
   - `filter_paths(paths: Iterable[Path]) -> Iterator[Path]`
   - Cached factory `get_ignore_manager(root: Path)`
   - Re-exports of DEFAULT_EXCLUDE_DIRS, DEFAULT_IGNORE_PATTERNS

2. Updated tools:
   - `glob.py` - use IgnoreManager
   - `list_dir.py` - use IgnoreManager
   - `grep_components/file_filter.py` - use IgnoreManager

3. Consolidated constants:
   - `indexing/constants.py` imports from tools/ignore.py

## Readiness

- [x] pathspec library installed (0.12.1)
- [x] Research doc reviewed and verified
- [x] Current implementation understood (3 tools, 1 duplicate)
- [x] Git state clean on branch `glob-improvements`

## Milestones

| ID | Milestone | Description |
|----|-----------|-------------|
| M1 | Core Module | Create ignore.py with IgnoreManager class |
| M2 | Tool Integration | Update glob, list_dir, grep to use IgnoreManager |
| M3 | Consolidation | Remove indexing/constants.py duplication |
| M4 | Validation | Tests pass, ruff clean, manual verification |

## Work Breakdown (Tasks)

### M1: Core Module

| ID | Task | Files | Acceptance Test |
|----|------|-------|-----------------|
| T1 | Create IgnoreManager class skeleton | `src/tunacode/tools/ignore.py` | Module imports without error |
| T2 | Implement should_ignore() with two-tier filtering | `src/tunacode/tools/ignore.py` | Fast path: dir name check. Slow path: pathspec match |
| T3 | Implement filter_paths() iterator | `src/tunacode/tools/ignore.py` | Yields only non-ignored paths |
| T4 | Add cached factory get_ignore_manager() | `src/tunacode/tools/ignore.py` | Same root returns cached instance; mtime change invalidates |
| T5 | Add .gitignore loading via pathspec | `src/tunacode/tools/ignore.py` | Parses root/.gitignore if exists |

### M2: Tool Integration

| ID | Task | Files | Acceptance Test |
|----|------|-------|-----------------|
| T6 | Update glob.py to use IgnoreManager | `src/tunacode/tools/glob.py` | `glob_files()` respects .gitignore patterns |
| T7 | Update list_dir.py to use IgnoreManager | `src/tunacode/tools/list_dir.py` | `list_dir()` filters via IgnoreManager |
| T8 | Update file_filter.py to use IgnoreManager | `src/tunacode/tools/grep_components/file_filter.py` | Grep excludes gitignored files |

### M3: Consolidation

| ID | Task | Files | Acceptance Test |
|----|------|-------|-----------------|
| T9 | Replace IGNORE_DIRS in indexing/constants.py | `src/tunacode/indexing/constants.py`, `src/tunacode/indexing/code_index.py` | IGNORE_DIRS imported from tools/ignore.py |

### M4: Validation

| ID | Task | Files | Acceptance Test |
|----|------|-------|-----------------|
| T10 | Run ruff check | All modified files | Zero errors |
| T11 | Run test suite | `tests/` | 304+ tests pass |
| T12 | Manual verification | - | glob/list_dir/grep respect .gitignore in tunacode repo |

## Task Dependencies

```
T1 -> T2 -> T3 -> T4 -> T5 (sequential: class must exist first)
T5 -> T6, T7, T8 (parallel: tools independent)
T6, T7, T8 -> T9 (consolidation after tools updated)
T9 -> T10 -> T11 -> T12 (validation sequential)
```

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| pathspec API differs from fnmatch behavior | Medium | Medium | Test with current ignore_patterns.py patterns first |
| Circular import tools/ -> utils/ | Low | High | tools/ignore.py only imports from utils/, not reverse |
| Cache invalidation race condition | Low | Low | Single-threaded access pattern; mtime sufficient |
| Performance regression from pathspec | Low | Medium | Retain fast-path dir name check before pathspec |

## Test Strategy

One test file: `tests/tools/test_ignore.py`

| Task | Test |
|------|------|
| T2 | `test_should_ignore_default_dirs()` - .git, node_modules, __pycache__ ignored |
| T3 | `test_filter_paths_excludes_ignored()` - iterator skips ignored |
| T4 | `test_cache_invalidation_on_mtime()` - mock mtime change triggers reload |
| T5 | `test_gitignore_patterns_loaded()` - patterns from .gitignore file applied |

## References

- Research: `memory-bank/research/2026-01-14_12-50-37_centralized-ignore-patterns.md`
- Current patterns: `src/tunacode/utils/system/ignore_patterns.py`
- pathspec docs: https://pypi.org/project/pathspec/
- ripgrep model: https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md

## Final Gate

- **Plan path:** `memory-bank/plan/2026-01-14_13-15-00_centralized-ignore-patterns.md`
- **Milestones:** 4
- **Tasks:** 12
- **Ready for coding:** Yes

**Next command:** `/context-engineer:execute "memory-bank/plan/2026-01-14_13-15-00_centralized-ignore-patterns.md"`
