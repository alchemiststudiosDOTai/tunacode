---
title: "Complexity Hotspot Refactoring – Plan"
phase: Plan
date: "2026-02-01T00:00:00Z"
owner: "claude"
parent_research: "memory-bank/research/2026-02-01_complexity-hotspots.md"
git_commit_at_plan: "c7efda89"
tags: [plan, refactoring, complexity]
---

## Goal

Refactor 4 D-grade complexity hotspots to improve maintainability and reduce cognitive load. Target: reduce McCabe complexity scores below threshold (25) for all functions.

**Non-goals:**
- No behavioral changes to external interfaces
- No performance optimizations beyond incidental improvements
- No new features or capabilities

## Scope & Assumptions

**In scope:**
- `dispatch_tools` (29 → target <20)
- `block_anchor_replacer` (27 → target <20)
- `process_node` (24 → target <20)
- `is_ignored` (23 → target <20)

**Out of scope:**
- Infrastructure/file_filter.py `is_ignored` (different signature, separate concern)
- Test file rewrites (existing tests must pass)
- Documentation updates beyond inline code clarity

**Assumptions:**
- Existing test coverage is sufficient for regression detection
- Functions can be decomposed without breaking public APIs
- Helper functions can be private (single underscore prefix)

## Deliverables (DoD)

1. **Refactored functions** with complexity <20 (measured by `uv run python scripts/cyclomatic_report.py`)
2. **All existing tests pass** (`uv run pytest`)
3. **No new mypy errors** (baseline maintained)
4. **Ruff clean** (`uv run ruff check .`)

## Readiness (DoR)

- [x] Research doc complete
- [x] Git state captured
- [x] Test files identified
- [x] Complexity measurement tool available

## Milestones

- **M1:** `dispatch_tools` decomposition (highest complexity, biggest impact)
- **M2:** `block_anchor_replacer` deduplication (similarity calculation extraction)
- **M3:** `process_node` response processing extraction
- **M4:** `is_ignored` rooted pattern flattening
- **M5:** Final validation & complexity re-measurement

## Work Breakdown (Tasks)

| Task | ID | Summary | File | Target Complexity | Acceptance Tests |
|------|-----|---------|------|-------------------|------------------|
| T1 | tk-new | Extract `_process_native_tool_calls` from `dispatch_tools` | tool_dispatcher.py | <10 | Existing dispatcher tests pass |
| T2 | tk-new | Extract `_execute_tool_batch` from `dispatch_tools` | tool_dispatcher.py | <8 | Tool execution tests pass |
| T3 | tk-new | Extract `_finalize_dispatch_state` from `dispatch_tools` | tool_dispatcher.py | <5 | State transition tests pass |
| T4 | tk-new | Extract `_calculate_similarity` from `block_anchor_replacer` | text_match.py | <8 | text_match tests pass |
| T5 | tk-new | Flatten nesting in `is_ignored` rooted patterns | ignore_patterns.py | <15 | ignore pattern tests pass |

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| Callback state corruption during extraction | High | Medium | Preserve exact callback invocation order; add debug assertions | Test failures in tool lifecycle tests |
| Generator semantics change in block_anchor_replacer | Medium | Low | Maintain `yield` structure; extract calculation only | text_match unit test failures |
| State machine transitions break | High | Low | Document pre/post conditions; verify transition table | orchestrator integration test failures |
| Merge conflicts with in-flight work | Medium | High | Small focused PRs; rebase frequently | PR review delays |

## Test Strategy

- **No new tests** - rely on existing coverage
- **Pre-commit validation:** `uv run pytest tests/integration/tools/test_tool_dispatcher_coverage.py tests/unit/core/test_text_match.py tests/integration/core/test_tool_call_lifecycle.py tests/tools/test_ignore.py -v`
- **Complexity gate:** `uv run python scripts/cyclomatic_report.py | grep -E "(dispatch_tools|block_anchor_replacer|process_node|is_ignored)"`

## References

- Research doc: `memory-bank/research/2026-02-01_complexity-hotspots.md`
- Target files:
  - `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`
  - `src/tunacode/tools/utils/text_match.py`
  - `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py`
  - `src/tunacode/configuration/ignore_patterns.py`
- Test files:
  - `tests/integration/tools/test_tool_dispatcher_coverage.py`
  - `tests/unit/core/test_text_match.py`
  - `tests/integration/core/test_tool_call_lifecycle.py`
  - `tests/tools/test_ignore.py`

## Tickets Created (max 5)

| Ticket ID | Title | Priority | Status |
|-----------|-------|----------|--------|
| tun-cd49 | Refactor dispatch_tools: extract native tool call processing | 1 | open |
| tun-c079 | Refactor dispatch_tools: extract tool batch execution | 2 | open |
| tun-748d | Refactor block_anchor_replacer: deduplicate similarity logic | 2 | open |
| tun-2e7b | Refactor is_ignored: flatten rooted pattern nesting | 3 | open |

## Dependencies

- tun-c079 depends on tun-cd49 (tool batch uses processed calls)
- tun-748d independent
- tun-2e7b independent
