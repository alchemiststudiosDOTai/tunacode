---
title: "Session Resume Module Refactor - Plan"
phase: Plan
date: "2026-01-21T16:15:00Z"
owner: "claude"
parent_research: "memory-bank/research/2026-01-21_15-27-57_session-resume-logic.md"
git_commit_at_plan: "c9b71bb"
tags: [plan, resume, session, compaction, refactor]
---

## Goal

Extract session resume logic from `main.py` into a dedicated `resume/` module and implement opencode-style rolling summaries for long conversations.

**Non-goals:**
- Changing message persistence format (keep JSON files in state.py)
- Adding new UI components
- Deployment/observability changes

## Scope & Assumptions

**In scope:**
- Move 5 sanitization functions from main.py to resume/
- Move compaction.py into resume/ module
- Implement rolling summary generation (summary checkpoints)
- Implement filterCompacted (history truncation at summary)
- Update main.py to import from new module

**Out of scope:**
- Changing StateManager or session persistence
- UI changes for summary display
- Multi-model summary generation

**Assumptions:**
- pydantic-ai message format stays stable
- Summary generation uses same model as conversation
- Summary trigger threshold: ~40k tokens (configurable)

## Deliverables

1. `src/tunacode/core/agents/resume/` module with:
   - `__init__.py` - public API exports
   - `sanitize.py` - 5 cleanup functions
   - `prune.py` - tool output pruning (moved from compaction.py)
   - `summary.py` - rolling summary generation
   - `filter.py` - filterCompacted equivalent

2. Updated `main.py` - imports from resume/, no embedded sanitization

3. Deleted `src/tunacode/core/compaction.py` (moved to resume/prune.py)

## Readiness

**Preconditions:**
- [x] Research doc complete
- [x] Git clean on resume-qa branch (only journal/research uncommitted)
- [x] Existing sanitization functions identified (5 total)
- [x] compaction.py analyzed

## Milestones

| ID | Milestone | Description |
|----|-----------|-------------|
| M1 | Module skeleton | Create resume/ directory, __init__.py, empty files |
| M2 | Move sanitize functions | Extract 5 functions to sanitize.py |
| M3 | Move prune functions | Move compaction.py to resume/prune.py |
| M4 | Implement summary | Add rolling summary generation |
| M5 | Implement filter | Add filterCompacted equivalent |
| M6 | Integration | Wire everything in main.py |

## Work Breakdown (Tasks)

### M1: Module Skeleton

| Task | Summary | Files | Acceptance |
|------|---------|-------|------------|
| T1.1 | Create resume/ directory structure | `resume/__init__.py`, `resume/sanitize.py`, `resume/prune.py`, `resume/summary.py`, `resume/filter.py` | `from tunacode.core.agents.resume import sanitize_history` imports without error |

### M2: Move Sanitize Functions

| Task | Summary | Files | Acceptance |
|------|---------|-------|------------|
| T2.1 | Move `_remove_consecutive_requests()` | `resume/sanitize.py`, `main.py` | Function works identically, main.py imports it |
| T2.2 | Move `_remove_empty_responses()` | `resume/sanitize.py`, `main.py` | Function works identically |
| T2.3 | Move `_strip_system_prompt_parts()` | `resume/sanitize.py`, `main.py` | Function works identically |
| T2.4 | Move `_sanitize_history_for_resume()` | `resume/sanitize.py`, `main.py` | Function works identically |
| T2.5 | Move `_remove_dangling_tool_calls()` + helpers | `resume/sanitize.py`, `main.py` | All 4 helper functions moved together |
| T2.6 | Add `run_cleanup_loop()` orchestrator | `resume/sanitize.py` | Encapsulates the iterative cleanup from main.py lines 370-428 |

### M3: Move Prune Functions

| Task | Summary | Files | Acceptance |
|------|---------|-------|------------|
| T3.1 | Move compaction.py to resume/prune.py | `resume/prune.py`, delete `core/compaction.py` | All imports updated, `prune_old_tool_outputs()` accessible |
| T3.2 | Update imports across codebase | Any file importing from compaction | `ruff check` passes, no import errors |

### M4: Implement Summary

| Task | Summary | Files | Acceptance |
|------|---------|-------|------------|
| T4.1 | Define summary message format | `resume/summary.py` | `SummaryMessage` dataclass with content, timestamp, source_range |
| T4.2 | Implement `is_summary_message()` | `resume/summary.py` | Detects summary checkpoint messages in history |
| T4.3 | Implement `generate_summary()` | `resume/summary.py` | Uses agent to summarize conversation, returns SummaryMessage |
| T4.4 | Implement `should_compact()` | `resume/summary.py` | Returns True if history exceeds SUMMARY_THRESHOLD tokens |

### M5: Implement Filter

| Task | Summary | Files | Acceptance |
|------|---------|-------|------------|
| T5.1 | Implement `filter_compacted()` | `resume/filter.py` | Scans backwards, stops at summary checkpoint, returns truncated history |
| T5.2 | Integrate filter with prune | `resume/filter.py` | `prepare_history()` calls filter then prune |

### M6: Integration

| Task | Summary | Files | Acceptance |
|------|---------|-------|------------|
| T6.1 | Update main.py imports | `main.py` | Imports from resume/, no embedded functions |
| T6.2 | Replace inline cleanup with `run_cleanup_loop()` | `main.py` | Lines 370-428 replaced with single call |
| T6.3 | Add summary trigger to request loop | `main.py` | After successful response, check `should_compact()` |
| T6.4 | Run full test suite | - | `uv run pytest` passes |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Summary generation uses tokens | Medium | Only trigger at high thresholds, make configurable |
| pydantic-ai message format changes | High | Type hints + tests catch breakage |
| Circular imports | Medium | Keep resume/ leaf module, no imports from main.py |

## Test Strategy

| Task | Test |
|------|------|
| T2.6 | Test `run_cleanup_loop()` with corrupt history fixture |
| T4.3 | Test `generate_summary()` with mock agent |
| T5.1 | Test `filter_compacted()` finds summary checkpoint |

## References

- Research: `memory-bank/research/2026-01-21_15-27-57_session-resume-logic.md`
- OpenCode compaction: `packages/opencode/src/session/compaction.ts`
- OpenCode summary: `packages/opencode/src/session/summary.ts`
- Journal: `.claude/JOURNAL.md` (2026-01-21 entries)

## Final Gate

- **Plan path:** `memory-bank/plan/2026-01-21_16-15-00_resume-module-refactor.md`
- **Milestone count:** 6
- **Task count:** 15
- **Ready for coding:** Yes

**Next command:** `/context-engineer:execute "memory-bank/plan/2026-01-21_16-15-00_resume-module-refactor.md"`

---

## Summary for User

### Milestones
1. **M1: Module skeleton** - Create `resume/` directory with empty files
2. **M2: Move sanitize functions** - Extract 5 cleanup functions from main.py
3. **M3: Move prune functions** - Relocate compaction.py into module
4. **M4: Implement summary** - Add rolling summary generation
5. **M5: Implement filter** - Add filterCompacted (history truncation)
6. **M6: Integration** - Wire everything together, run tests

### Key Tasks
- T1.1: Create directory structure
- T2.1-T2.6: Move sanitization functions (6 tasks)
- T3.1-T3.2: Move pruning logic (2 tasks)
- T4.1-T4.4: Implement summaries (4 tasks)
- T5.1-T5.2: Implement filtering (2 tasks)
- T6.1-T6.4: Final integration (4 tasks)

### Architecture
```
src/tunacode/core/agents/
├── resume/
│   ├── __init__.py      # Public API: prepare_history, run_cleanup_loop
│   ├── sanitize.py      # 5 cleanup functions
│   ├── prune.py         # Tool output pruning (from compaction.py)
│   ├── summary.py       # Rolling summary generation
│   └── filter.py        # filterCompacted equivalent
├── main.py              # Imports from resume/
└── ...
```
