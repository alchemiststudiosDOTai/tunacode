---
title: "renderer taxonomy cleanup implementation plan"
link: "renderer-taxonomy-cleanup-plan"
type: implementation_plan
ontological_relations:
  - relates_to: [[renderer-taxonomy-cleanup-research]]
tags: [plan, renderer-taxonomy-cleanup, coding]
uuid: "eccc5900-80ad-42c7-9194-584201135bb6"
created_at: "2026-04-27T14:34:58-05:00"
parent_research: ".artifacts/research/2026-04-27_14-34-08_renderer-taxonomy-cleanup.md"
git_commit_at_plan: "de44031a"
---

## Goal

- Clean `src/tunacode/ui/renderers/errors.py` so the renderer taxonomy classifies only currently meaningful TunaCode error names and no longer carries undefined or unraised legacy entries.
- Out of scope: deleting additional exception classes from `src/tunacode/exceptions.py`, changing tool failure semantics, changing user-facing panel layout, or redesigning exception message formatting.

## Scope & Assumptions

- IN scope:
  - Remove renderer-only taxonomy entries with no current exception definition or production raise site.
  - Remove renderer imports and pattern matches for exception classes with no production raise site.
  - Preserve renderer behavior for currently raised errors: `ToolExecutionError`, `FileOperationError`, `AgentError`, `GlobalRequestTimeoutError`, `ContextOverflowError`, `ConfigurationError`, and `UserAbortError`.
  - Preserve `ValidationError` renderer metadata handling in this pass because the class still has explicit formatting tests and a structured `suggested_fix` interface.
- OUT of scope:
  - Removing `GitOperationError`, `ModelConfigurationError`, `SetupValidationError`, `StateError`, `ServiceError`, `ToolBatchingJSONError`, or `ValidationError` from `src/tunacode/exceptions.py`.
  - Moving exception presentation out of `src/tunacode/exceptions.py`.
  - Consolidating tool error contracts.
- Assumptions:
  - The current source already has `TooBroadPatternError` and `AggregateToolError` removed from `src/tunacode/exceptions.py`.
  - `render_exception` may still receive unknown exception names, and those should continue to fall back to severity `"error"`.
  - `uv` and the repository `.venv` are available.

## Deliverables

- Updated `src/tunacode/ui/renderers/errors.py` with a smaller active taxonomy.
- Updated focused tests in `tests/unit/core/test_provider_error_surfacing.py`.
- No new public modules or broad docs changes.

## Readiness

- Preconditions:
  - Research artifact exists at `.artifacts/research/2026-04-27_14-34-08_renderer-taxonomy-cleanup.md`.
  - Current git state at plan time:
    - `M AGENTS.md`
    - `M src/tunacode/exceptions.py`
    - `?? .artifacts/research/2026-04-27_14-23-50_exceptions-map.md`
    - `?? .artifacts/research/2026-04-27_14-34-08_renderer-taxonomy-cleanup.md`
- What must exist before starting:
  - `src/tunacode/ui/renderers/errors.py`
  - `tests/unit/core/test_provider_error_surfacing.py`

## Milestones

- M1: Remove undefined and string-only renderer taxonomy entries.
- M2: Remove unraised imported renderer special cases.
- M3: Lock the intended taxonomy with focused tests.
- M4: Run focused validation.

## Ticket Index

<!-- TICKET_INDEX:START -->

| Task | Title | Ticket |
|---|---|---|
| T001 | Remove undefined and string-only renderer taxonomy entries | [tickets/T001.md](tickets/T001.md) |
| T002 | Remove unraised imported renderer special cases | [tickets/T002.md](tickets/T002.md) |
| T003 | Add a focused renderer taxonomy regression test | [tickets/T003.md](tickets/T003.md) |
| T004 | Run focused exception renderer validation | [tickets/T004.md](tickets/T004.md) |

<!-- TICKET_INDEX:END -->

## Work Breakdown (Tasks)

### T001: Remove undefined and string-only renderer taxonomy entries

**Summary**: Remove renderer taxonomy entries that are not backed by a current exception definition or any production raise site.

**Owner**: engineer

**Estimate**: 20m

**Dependencies**: none

**Target milestone**: M1

**Acceptance test**: `rg -n "\\b(AuthenticationError|StateError|ToolBatchingJSONError)\\b" src/tunacode/ui/renderers/errors.py` returns no matches.

**Files/modules touched**:
- `src/tunacode/ui/renderers/errors.py`

**Steps**:
1. Remove `AuthenticationError`, `StateError`, and `ToolBatchingJSONError` from `ERROR_SEVERITY_MAP`.
2. Remove `AuthenticationError` from `DEFAULT_RECOVERY_COMMANDS`.
3. Do not change `render_exception` fallback behavior for unknown exception types.

### T002: Remove unraised imported renderer special cases

**Summary**: Remove renderer imports, pattern matches, and default recovery commands for exception classes that exist but have no production raise site.

**Owner**: engineer

**Estimate**: 30m

**Dependencies**: T001

**Target milestone**: M2

**Acceptance test**: `uv run ruff check src/tunacode/ui/renderers/errors.py` passes.

**Files/modules touched**:
- `src/tunacode/ui/renderers/errors.py`

**Steps**:
1. Remove imports for `GitOperationError`, `ModelConfigurationError`, and `SetupValidationError`.
2. Remove `GitOperationError`, `ModelConfigurationError`, and `SetupValidationError` keys from `ERROR_SEVERITY_MAP`.
3. Remove `ModelConfigurationError` and `GitOperationError` keys from `DEFAULT_RECOVERY_COMMANDS`.
4. Remove the pattern match branches for `GitOperationError`, `ModelConfigurationError`, and `SetupValidationError`.
5. Keep the `ContextOverflowError` context branch as a standalone match returning `{"Model": str(model)}`.

### T003: Add a focused renderer taxonomy regression test

**Summary**: Add a focused test that records the active renderer taxonomy and rejects the removed stale names.

**Owner**: engineer

**Estimate**: 25m

**Dependencies**: T002

**Target milestone**: M3

**Acceptance test**: `uv run pytest tests/unit/core/test_provider_error_surfacing.py -k taxonomy` passes.

**Files/modules touched**:
- `tests/unit/core/test_provider_error_surfacing.py`

**Steps**:
1. Add a test named `test_error_severity_map_contains_only_active_taxonomy`.
2. Assert `ERROR_SEVERITY_MAP` equals this explicit set: `ToolExecutionError`, `FileOperationError`, `AgentError`, `GlobalRequestTimeoutError`, `ContextOverflowError`, `ConfigurationError`, `ValidationError`, `UserAbortError`.
3. Do not add mocks or broad UI snapshot tests.

### T004: Run focused exception renderer validation

**Summary**: Run the focused checks that cover exception formatting, provider error surfacing, renderer taxonomy, and the touched renderer file.

**Owner**: engineer

**Estimate**: 15m

**Dependencies**: T003

**Target milestone**: M4

**Acceptance test**: `uv run pytest tests/unit/core/test_exceptions.py tests/unit/core/test_provider_error_surfacing.py` passes.

**Files/modules touched**:
- `src/tunacode/ui/renderers/errors.py`
- `tests/unit/core/test_provider_error_surfacing.py`
- `tests/unit/core/test_exceptions.py`

**Steps**:
1. Run `uv run pytest tests/unit/core/test_exceptions.py tests/unit/core/test_provider_error_surfacing.py`.
2. Run `uv run ruff check src/tunacode/exceptions.py src/tunacode/ui/renderers/errors.py tests/unit/core/test_provider_error_surfacing.py`.
3. Run `uv run python scripts/check_agents_freshness.py`.
4. If any check fails outside the touched surface, stop and report the exact blocker.

## Risks & Mitigations

- Risk: a future unraised exception type loses special UI context.
  - Mitigation: `render_exception` still falls back to generic severity `"error"` and message rendering.
- Risk: `ValidationError` has no current production raise site but retains renderer handling.
  - Mitigation: keep it in this pass because it has a structured metadata interface and existing formatting tests.
- Risk: removing renderer recovery commands may reduce guidance if an unraised legacy class is manually instantiated.
  - Mitigation: this pass is scoped to current production behavior; exception class deletion is a separate decision.

## Test Strategy

- Add one focused taxonomy test in `tests/unit/core/test_provider_error_surfacing.py`.
- Re-run existing exception formatting and provider error surfacing tests.
- Run ruff on touched Python files.

## References

- `.artifacts/research/2026-04-27_14-34-08_renderer-taxonomy-cleanup.md`
- `src/tunacode/ui/renderers/errors.py:23`
- `src/tunacode/ui/renderers/errors.py:41`
- `src/tunacode/ui/renderers/errors.py:73`
- `tests/unit/core/test_provider_error_surfacing.py:30`

## Final Gate

- **Output summary**: plan dir path, milestone count, ticket count
- **Next step**: proceed to execute-phase with `.artifacts/plan/2026-04-27_14-34-08_renderer-taxonomy-cleanup/PLAN.md`
