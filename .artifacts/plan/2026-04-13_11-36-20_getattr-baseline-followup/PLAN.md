---
title: "getattr baseline followup implementation plan"
link: "getattr-baseline-followup-plan"
type: implementation_plan
ontological_relations:
  - relates_to: [[getattr-baseline-followup-research]]
tags: [plan, getattr, ast-grep, coding]
uuid: "10cd320d-3772-4f41-ae08-a7a594e851e5"
created_at: "2026-04-13T11:36:20-05:00"
parent_research: ".artifacts/research/2026-04-13_11-26-27_getattr-baseline-followup.md"
git_commit_at_plan: "e7082197"
---

## Goal

- Reduce the `no-getattr-in-src` baseline with small, independently landable refactors that replace defensive `getattr(...)` calls on already-typed TunaCode app, session, and exception surfaces.
- Keep each slice biased toward net code reduction in the touched files by deleting fallback branches instead of adding new shim layers.
- Out of scope: lazy export loader redesigns, generic third-party exception normalization, command-loader reflection changes, and broad message/tool payload contract rewrites.

## Scope & Assumptions

- IN scope: `LogManager.debug_mode`, `RequestDebugTracer`, `thinking_state`, `Editor.on_key`, `TextualReplApp.action_cancel_request`, `is_widget_within_field`, and TunaCode-owned exception rendering in `ui/renderers/errors.py`.
- IN scope: focused regression updates or new narrow unit tests that prove the direct-access paths still behave correctly.
- OUT of scope: `src/tunacode/core/types/__init__.py`, `src/tunacode/ui/renderers/__init__.py`, `src/tunacode/ui/widgets/__init__.py`, `src/tunacode/ui/command_registry.py`, `src/tunacode/ui/clipboard.py`, `src/tunacode/ui/renderers/panels.py`, `src/tunacode/utils/messaging/token_counter.py`, and `src/tunacode/core/compaction/controller.py`.
- OUT of scope: introducing new cross-cutting protocols, helper wrappers, or abstraction layers solely to replace `getattr(...)`.
- Assumptions: `TextualReplApp` remains the concrete source of truth for `request_queue`, `editor`, `_last_editor_keypress_at`, and `_shell_runner`; `StateManagerProtocol.session.debug_mode` remains the source of truth for debug gating; TunaCode-owned exceptions in `src/tunacode/exceptions.py` keep their existing typed attributes.
- Assumptions: line-count reduction is a secondary success constraint for every slice, but correctness and low blast radius still take precedence.
- Assumptions: the working tree at plan time contains only the untracked parent research artifact.

## Deliverables

- A plan bundle that removes a scoped subset of baseline `getattr(...)` entries from UI/runtime and owned-exception paths.
- Focused unit coverage proving the direct-access paths still work with concrete app/session/test-double contracts.
- A refreshed ast-grep baseline file and `AGENTS.md` entry that reflect the reduced finding count after the scoped removals land.

## Readiness

- Preconditions: the parent research artifact exists at `.artifacts/research/2026-04-13_11-26-27_getattr-baseline-followup.md`.
- Preconditions: the plan snapshot is based on Git commit `e7082197`.
- Preconditions: `docs/git/practices.md` has already been read in this session before Git inspection.
- Preconditions: no cleanup of untracked files is required; the only untracked path observed during planning is `.artifacts/research/2026-04-13_11-26-27_getattr-baseline-followup.md`.

## Milestones

- M1: Debug-mode and request-queue slices use direct typed access.
- M2: Editor/thinking/app helper slices use direct UI contracts without lifecycle guesswork.
- M3: Owned exception rendering stops reflecting over TunaCode exception fields.
- M4: Baseline and metadata are refreshed to match the reduced scoped findings.

## Ticket Index

<!-- TICKET_INDEX:START -->

| Task | Title | Ticket |
|---|---|---|
| T001 | bug: simplify LogManager debug-mode access | [tickets/T001.md](tickets/T001.md) |
| T002 | bug: remove RequestDebugTracer session and queue probing | [tickets/T002.md](tickets/T002.md) |
| T003 | bug: remove editor and thinking-state getattr fallbacks | [tickets/T003.md](tickets/T003.md) |
| T004 | bug: simplify remaining direct-UI contract helpers | [tickets/T004.md](tickets/T004.md) |
| T005 | bug: render TunaCode-owned exceptions through explicit attributes | [tickets/T005.md](tickets/T005.md) |
| T006 | chore: refresh getattr baseline and AGENTS metadata | [tickets/T006.md](tickets/T006.md) |

<!-- TICKET_INDEX:END -->

## Work Breakdown (Tasks)

### T001: bug: simplify LogManager debug-mode access

**Summary**: Replace the defensive `getattr(...)` call in `LogManager.debug_mode` with direct access to `StateManagerProtocol.session.debug_mode`, keeping the property small and aligned with the protocol already defined in `core/types/state.py`.

**Owner**: core

**Estimate**: 45m

**Dependencies**: none

**Target milestone**: M1

**Acceptance test**: `uv run pytest tests/unit/core/test_logging.py -k lifecycle_gated_by_debug_mode`

**Files/modules touched**:
- src/tunacode/core/logging/manager.py
- tests/unit/core/test_logging.py

**Steps**:
1. Replace the `getattr(self._state_manager.session, "debug_mode", False)` branch in `src/tunacode/core/logging/manager.py` with direct protocol access once `_state_manager` is known to be present.
2. Keep the `None` state-manager fast path intact so logger bootstrap behavior stays unchanged before a session is attached.
3. Tighten or add a unit assertion in `tests/unit/core/test_logging.py` so the debug gate proves the property reads the real session attribute rather than a fallback probe.
4. Avoid introducing helper accessors or new protocol layers; this slice should shrink the property rather than wrap it.

### T002: bug: remove RequestDebugTracer session and queue probing

**Summary**: Simplify `RequestDebugTracer` so debug enablement and queue sizing use the concrete `TextualReplApp.state_manager.session` and `TextualReplApp.request_queue` contracts instead of probing for optional attributes.

**Owner**: ui

**Estimate**: 1.5h

**Dependencies**: T001

**Target milestone**: M1

**Acceptance test**: `uv run pytest tests/unit/ui/test_request_debug.py -k request_debug`

**Files/modules touched**:
- src/tunacode/ui/request_debug.py
- tests/unit/ui/test_request_debug.py

**Steps**:
1. Replace the `_enabled` path in `src/tunacode/ui/request_debug.py` so it reads `self._app.state_manager.session.debug_mode` directly.
2. Collapse `_queue_size()` to the public queue contract already present on `TextualReplApp`, preferring `request_queue.qsize()` and deleting the fallback probe for `items`.
3. Keep the tracer behavior unchanged for existing unit-test fakes by updating the fake app or fake queue types in `tests/unit/ui/test_request_debug.py` instead of restoring reflective access in production code.
4. Confirm this slice removes lines overall by deleting the fallback branches rather than moving them into helper functions.

### T003: bug: remove editor and thinking-state getattr fallbacks

**Summary**: Replace `getattr(...)` usage in `ui/thinking_state.py` and `ui/widgets/editor.py` with direct access to the already-owned app/editor state, while preserving the current behavior around recent keypress throttling and paste-buffer handling.

**Owner**: ui

**Estimate**: 2h

**Dependencies**: T002

**Target milestone**: M2

**Acceptance test**: `uv run pytest tests/unit/ui/test_thinking_state.py tests/unit/utils/test_shell_command_escape.py -k "thinking or bang"`

**Files/modules touched**:
- src/tunacode/ui/thinking_state.py
- src/tunacode/ui/widgets/editor.py
- tests/unit/ui/test_thinking_state.py
- tests/unit/utils/test_shell_command_escape.py

**Steps**:
1. In `src/tunacode/ui/thinking_state.py`, replace the `app.editor`, `editor.value`, and `app._last_editor_keypress_at` probes with direct reads from the concrete `TextualReplApp` surface.
2. In `src/tunacode/ui/widgets/editor.py`, remove the fallback probes around `self.app`, `app._request_debug`, and `self.has_paste_buffer`, keeping only the lifecycle guard that is actually required when the widget is unattached.
3. Update the editor/thinking tests so their fakes expose the concrete fields directly, matching the runtime contract instead of relying on missing-attribute fallbacks.
4. Keep this slice local to the editor/thinking flow; do not introduce shared access helpers that would spread the change into unrelated widgets.

### T004: bug: simplify remaining direct-UI contract helpers

**Summary**: Clean up the remaining low-risk UI helpers by using direct access for `TextualReplApp._shell_runner` in request cancellation and `DOMNode.id` in context-panel ancestry checks.

**Owner**: ui

**Estimate**: 1.5h

**Dependencies**: T003

**Target milestone**: M2

**Acceptance test**: `uv run pytest tests/unit/utils/test_shell_command_escape.py tests/unit/ui/test_context_panel.py -k "cancel or within_field"`

**Files/modules touched**:
- src/tunacode/ui/app.py
- src/tunacode/ui/context_panel.py
- tests/unit/utils/test_shell_command_escape.py
- tests/unit/ui/test_context_panel.py

**Steps**:
1. Replace `getattr(self, "_shell_runner", None)` in `TextualReplApp.action_cancel_request()` with direct field access, preserving the current lazy-initialization behavior by passing the stored optional runner as-is.
2. Replace `getattr(current, "id", None)` in `src/tunacode/ui/context_panel.py` with direct `DOMNode.id` access while keeping the parent walk unchanged.
3. Extend `tests/unit/utils/test_shell_command_escape.py` with an app-cancel regression that exercises the direct `_shell_runner` field path.
4. Add `tests/unit/ui/test_context_panel.py` with a narrow ancestry regression so the helper remains covered after the fallback branch is deleted.

### T005: bug: render TunaCode-owned exceptions through explicit attributes

**Summary**: Refactor `ui/renderers/errors.py` so TunaCode-owned exception types are rendered from explicit, known attributes instead of reflective `getattr(...)` probes, while leaving generic foreign-exception introspection out of scope.

**Owner**: ui

**Estimate**: 2h

**Dependencies**: none

**Target milestone**: M3

**Acceptance test**: `uv run pytest tests/unit/core/test_exceptions.py tests/unit/core/test_provider_error_surfacing.py -k "render_exception or context_overflow"`

**Files/modules touched**:
- src/tunacode/ui/renderers/errors.py
- tests/unit/core/test_exceptions.py
- tests/unit/core/test_provider_error_surfacing.py

**Steps**:
1. Enumerate the TunaCode-owned exception classes that already carry typed fields in `src/tunacode/exceptions.py` and use explicit attribute reads for `suggested_fix`, `recovery_commands`, and context fields when `render_exception()` sees those classes.
2. Keep the severity mapping and message-cleanup behavior unchanged; this slice is about removing reflective field probing, not redesigning the rendered panel shape.
3. Leave truly generic third-party exception inspection out of scope for this task; do not add a new cross-cutting exception protocol just to normalize arbitrary foreign errors.
4. Add or tighten regression assertions in the exception/provider tests so the renderer still surfaces owned exception metadata after the reflective probes are removed.

### T006: chore: refresh getattr baseline and AGENTS metadata

**Summary**: After the scoped source changes land, rewrite the ast-grep baseline to capture the reduced `getattr(...)` count, update `AGENTS.md` for the touched `src/` files, and keep the repository metadata aligned with the new baseline.

**Owner**: chore

**Estimate**: 45m

**Dependencies**: T001,T002,T003,T004,T005

**Target milestone**: M4

**Acceptance test**: `uv run python scripts/check_agents_freshness.py && uv run python scripts/check_ast_grep_baseline.py`

**Files/modules touched**:
- AGENTS.md
- rules/ast-grep/baseline/no-getattr-in-src.json

**Steps**:
1. Run `uv run python scripts/check_ast_grep_baseline.py --write-baseline` after the scoped slices are complete so `rules/ast-grep/baseline/no-getattr-in-src.json` reflects the lower finding count.
2. Inspect the baseline diff and keep it limited to the targeted removals from this plan; if unrelated findings move, stop and reconcile before proceeding.
3. Update `AGENTS.md` with a new `Last Updated` date and a concise note that the getattr-baseline follow-up reduced scoped UI/runtime and owned-exception `getattr(...)` usage.
4. Finish by running the freshness script and the non-write ast-grep baseline check so the metadata and ratchet state agree.

## Risks & Mitigations

- Risk: direct attribute access could fail in tests that currently omit concrete fields from fake app/session objects.
  Mitigation: update the test doubles to match the real runtime contract instead of reintroducing production fallbacks.
- Risk: the request-debug queue path may rely on private queue internals for one debug-only metric.
  Mitigation: keep the slice on public queue APIs first and verify the metric still has a deterministic unit-test proof before deleting any fallback.
- Risk: the exception-rendering slice could accidentally broaden into a generic exception contract redesign.
  Mitigation: limit the explicit-attribute path to TunaCode-owned exception classes and leave foreign-exception reflection as a separate follow-up.
- Risk: line-count reduction could get lost if implementation replaces each `getattr(...)` with helper wrappers or new shims.
  Mitigation: require every slice to delete fallback branches locally and treat helper-sprawl as a plan violation.
- Risk: the final baseline rewrite may hide unrelated movement if execution includes extra `getattr(...)` edits outside this scope.
  Mitigation: inspect the baseline diff entry-by-entry before accepting the rewrite and stop if unrelated files changed.

## Test Strategy

- Add at most one focused regression proof per task and keep the tests in the nearest existing module unless a tiny new file is cleaner.
- Prefer concrete fake objects that expose the same attributes as `TextualReplApp`, `StateManager.session`, and TunaCode exceptions.
- Use focused `pytest -k` commands as the task proof so each slice can land independently without running the full suite first.

## References

- Research doc: `.artifacts/research/2026-04-13_11-26-27_getattr-baseline-followup.md`
- `src/tunacode/core/logging/manager.py:82` for `LogManager.debug_mode`
- `src/tunacode/core/types/state.py:24` for `SessionStateProtocol`
- `src/tunacode/ui/request_debug.py:395` for tracer debug-mode and queue access
- `src/tunacode/ui/thinking_state.py:14` for thinking draft/key-press checks
- `src/tunacode/ui/widgets/editor.py:80` for editor key handling and paste-buffer logic
- `src/tunacode/ui/app.py:626` for `action_cancel_request()`
- `src/tunacode/ui/context_panel.py:176` for `is_widget_within_field()`
- `src/tunacode/ui/renderers/errors.py:38` for exception context extraction
- `src/tunacode/exceptions.py:94` for TunaCode-owned exception fields
- `rules/ast-grep/baseline/no-getattr-in-src.json`
- `scripts/check_ast_grep_baseline.py`
- `tests/unit/core/test_logging.py:241` for logger debug gating coverage
- `tests/unit/ui/test_request_debug.py:38` for request-debug regressions
- `tests/unit/ui/test_thinking_state.py:48` for thinking-state fakes
- `tests/unit/utils/test_shell_command_escape.py:84` for cancel/editor regressions

## Final Gate

- **Output summary**: `.artifacts/plan/2026-04-13_11-36-20_getattr-baseline-followup/`, 4 milestones, 6 tickets
- **Next step**: proceed to execute-phase with `.artifacts/plan/2026-04-13_11-36-20_getattr-baseline-followup/PLAN.md`
