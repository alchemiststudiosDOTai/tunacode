---
title: "Issue #358 – Tool Dispatcher Complexity Reduction Plan"
phase: Plan
date: "2026-02-05T00:00:00Z"
owner: "tuna"
parent_research: "memory-bank/research/2026-02-05_tool_dispatcher_complexity_358.md"
git_commit_at_plan: "9ed9739d"
tags: [plan, refactor, complexity, tool-dispatcher, orchestrator, issue-358]
---

## Objective

Reduce cognitive load and maintenance risk in:
`src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`

Primary drivers from research (#358):
- Unused parameters in `_collect_structured_tool_calls`
- Magic numbers for debug preview truncation and ms conversion
- Overloaded module responsibilities (collection + registry + execution + logging)

## Non-goals

- No user-visible behavior changes
- No new tool call formats / parsing rules
- No state-machine ownership changes (orchestrator still drives transitions)
- No new dependencies

## Success Criteria (Definition of Done)

1. **Dead parameters removed** and call sites updated.
2. **Magic numbers removed** (replaced with named constants).
3. **Assertions replaced** where they act as runtime type checks (asserts can be stripped with `-O`).
4. **All existing tests pass**:
   - `uv run pytest tests/integration/tools/test_tool_dispatcher_coverage.py`
   - `uv run pytest tests/integration/core/test_tool_call_lifecycle.py`
5. **Ruff clean**: `uv run ruff check --fix .`
6. **No new type-checking regressions introduced** (keep mypy error count from increasing).

## Constraints / Project Rules

- Small, focused diffs; commit frequently.
- Fail fast, fail loud (no silent fallbacks).
- Keep identical things identical (normalize naming + constants consistently).
- Do not introduce new mypy errors.

## Work Plan (Phased)

### Phase 0 — Baseline + Guardrails (no behavior changes)
**Goal:** lock in baseline behavior + metrics so we can refactor safely.

Tasks:
- [ ] Confirm current tests are green for the two integration files.
- [ ] Capture before/after metrics in PR description (file lines, function count, magic literals count).

Acceptance:
- Tests pass before changes.

---

### Phase 1 — Extract Constants (low risk)
**Goal:** remove magic literals and document intent.

Changes:
- [ ] Add module constants:
  - `DEBUG_PREVIEW_MAX_LENGTH = 100`
  - `MS_PER_SECOND = 1000`
- [ ] Replace occurrences:
  - `tool_name[:100]`, `str(... )[:100]`, `text_content[:100]`
  - `* 1000` in elapsed-ms calculation

Acceptance:
- Tests pass.
- Diff is strictly mechanical (no logic changes).

---

### Phase 2 — Remove Dead Parameters (low risk)
**Goal:** reduce misleading API surface.

Changes:
- [ ] Update `_collect_structured_tool_calls` signature to remove unused parameters:
  - remove `node`
  - remove `tool_callback`
- [ ] Update internal call site in `dispatch_tools`.

Acceptance:
- Tests pass.
- No other callers exist (verify via ripgrep).

---

### Phase 3 — Replace Runtime-Type `assert` with Explicit Errors (behavior-preserving)
**Goal:** assertions currently enforce runtime contracts; they should fail loudly even under `python -O`.

Changes (in `_collect_fallback_tool_calls`):
- [ ] Replace:
  - `assert isinstance(result, tuple)`
  - `assert isinstance(result, list)`
  with explicit checks and a raised exception type that won’t be optimized away.

Proposed error type:
- Prefer `StateError` with a clear message, unless a more precise local exception exists.

Acceptance:
- Tests pass.
- Failure mode remains loud and actionable.

---

### Phase 4 — Module Responsibility Split (medium risk, still behavior-preserving)
**Goal:** make `tool_dispatcher.py` read like an orchestrator, not a grab bag.

Proposed structure (private modules; names are suggestions):
- `tool_dispatch_collection.py`
  - `_collect_structured_tool_calls`
  - `_collect_fallback_tool_calls`
- `tool_dispatch_registry_ops.py`
  - `_register_tool_call`, `_mark_tool_calls_running`, `_record_tool_failure`
- `tool_dispatch_logging.py`
  - `_log_dispatch_summary`

Constraints:
- Keep the public API stable: `dispatch_tools`, `has_tool_calls`, `consume_tool_call_args`, `record_tool_call_args`, `normalize_tool_args`.
- Avoid introducing circular imports (keep deferred imports if needed).

Acceptance:
- Tests pass.
- `tool_dispatcher.py` is meaningfully smaller and reads as a 4-phase dispatcher.

---

### Phase 5 — Optional: Introduce a `ToolDispatcher` Object (high risk / optional)
**Goal:** reduce parameter threading (`node`, `state_manager`, callbacks) by bundling into an explicit object.

Only do this if Phase 4 still leaves the module hard to navigate.

Acceptance:
- No public API change (module-level `dispatch_tools(...)` can instantiate and delegate).
- Tests pass.

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Circular imports when splitting modules | High | Medium | Keep deferred imports; move only leaf functions first; run import-time smoke test |
| Silent behavior change in fallback parser | High | Low | Keep logic identical; only replace asserts with explicit raises; rely on existing integration tests |
| Refactor causes new type errors | Medium | Medium | Prefer explicit types; keep changes small; run targeted tests frequently |

## Execution Checklist (per phase)

- [ ] `uv run ruff check --fix .`
- [ ] `uv run pytest tests/integration/tools/test_tool_dispatcher_coverage.py -q`
- [ ] `uv run pytest tests/integration/core/test_tool_call_lifecycle.py -q`

## References

- Research: `memory-bank/research/2026-02-05_tool_dispatcher_complexity_358.md`
- Target module: `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`
- Orchestrator: `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py`
- Tests:
  - `tests/integration/tools/test_tool_dispatcher_coverage.py`
  - `tests/integration/core/test_tool_call_lifecycle.py`
