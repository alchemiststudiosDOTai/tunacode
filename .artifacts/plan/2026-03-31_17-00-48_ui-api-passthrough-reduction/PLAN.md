---
title: "ui_api passthrough reduction implementation plan"
link: "ui-api-passthrough-reduction-plan"
type: implementation_plan
ontological_relations:
  - relates_to: [[core-ui-api-research]]
tags: [plan, ui-api, coding]
uuid: "beacadf7-d151-4cdc-88a5-209eeec2b7e4"
created_at: "2026-03-31T17:00:48Z"
refreshed_at: "2026-04-01T23:00:10Z"
parent_research: ".artifacts/research/2026-03-31_16-51-07_ui-api.md"
git_commit_at_plan: "27b7835e"
previous_plan_commit: "a65e7bf1"
artifact_commit_note: "User reported local artifact commit 70226786f200a0016b21d070078c21f8e423998e with push blocked by the pre-push empty-dir-check on ui/headless."
---

## Goal

- Reduce `src/tunacode/core/ui_api/` to only modules that add adapter behavior, by migrating UI callers off pure passthrough facades and deleting the dead facade modules.
- Keep runtime behavior, model/config workflows, and tool rendering behavior unchanged while simplifying import paths.
- Out of scope: redesigning the underlying configuration/types/utils APIs, changing request orchestration, or removing the non-trivial adapters (`file_filter.py`, `formatting.py`, `lsp_status.py`).

## Scope & Assumptions

- IN scope:
  - Replace UI imports of `core.ui_api` passthrough modules with direct imports from `tunacode.constants`, `tunacode.types`, `tunacode.configuration.*`, and `tunacode.utils.messaging`.
  - Delete the pure passthrough modules once no in-repo source file imports them.
  - Update only source-level docstrings/comments inside surviving `core/ui_api` modules when their wording would otherwise become false.
  - Add one architecture ratchet that locks the reduced `core/ui_api` file set.
- OUT of scope:
  - Moving logic between lower layers.
  - Reworking `FileFilter`, `LspServerInfo`, or diagnostic formatting behavior.
  - Any changes to tool callbacks, message schemas, or pricing/model registry logic beyond import-path updates.
  - Markdown docs, `AGENTS.md`, and generated structure artifacts; those land in a separate follow-up PR.
  - Ops/deploy/release work.
- Assumptions:
  - Direct UI imports from `configuration`, `types`, `constants`, and `utils` remain valid per `tests/test_dependency_layers.py:11-34` and `docs/modules/utils/utils.md:1-23`.
  - The modules identified as passthrough-only in the research doc stay behaviorally identical to their underlying implementations during this refactor.
  - Planning inputs at `.artifacts/research/2026-03-31_11-32-31_theme-switch-dim-background-crash.md` and `.artifacts/research/2026-03-31_16-51-07_ui-api.md` are informational only and should stay untouched during execution.

## Deliverables

- UI source files importing lower-layer modules directly instead of the removable `core.ui_api` facades.
- A narrowed `src/tunacode/core/ui_api/` package containing only `__init__.py`, `file_filter.py`, `formatting.py`, and `lsp_status.py`.
- One architecture test that ratchets the reduced `ui_api` surface.
- Source-level docstrings/comments in surviving `core/ui_api` modules aligned with the adapter-only package contract.

## Readiness

- Preconditions:
  - Research artifact exists at `.artifacts/research/2026-03-31_16-51-07_ui-api.md`.
  - Current workspace baseline was re-checked at clean commit `27b7835e`; the original plan bundle was created at `a65e7bf1`, so executors should re-run the planned `rg` call-site checks before editing if the branch moves again.
  - User-supplied artifact context referenced commit `70226786f200a0016b21d070078c21f8e423998e` and a pre-push `empty-dir-check` failure on `ui/headless`; treat that hook failure as a separate blocker, not a reason to widen this refactor.
  - The following checks are available for post-change validation: `tests/test_dependency_layers.py`, `tests/architecture/test_layer_dependencies.py`, `tests/architecture/test_import_order.py`.
- Before starting execution:
  - Keep the existing import order conventions in touched files.
  - Do not delete the research artifacts listed above.
  - Preserve `src/tunacode/core/ui_api/file_filter.py`, `src/tunacode/core/ui_api/formatting.py`, and `src/tunacode/core/ui_api/lsp_status.py` unless a later approved plan explicitly targets them.
  - If the pre-push `empty-dir-check` still fails after this refactor, stop and ask for direction instead of deleting directories as a workaround.

## Milestones

- M1: Migrate startup/model-selection UI paths off passthrough facades.
- M2: Migrate runtime/rendering UI paths off passthrough facades.
- M3: Delete dead `core/ui_api` modules and narrow the package surface.
- M4: Add a ratchet test and fix now-false source docstrings for the reduced surface.

## Ticket Index

<!-- TICKET_INDEX:START -->

| Task | Title | Ticket |
|---|---|---|
| T001 | Migrate startup and model-selection flows off passthrough facades | [tickets/T001.md](tickets/T001.md) |
| T002 | Migrate runtime and rendering flows off passthrough facades | [tickets/T002.md](tickets/T002.md) |
| T003 | Delete dead facade modules and narrow the `core/ui_api` package surface | [tickets/T003.md](tickets/T003.md) |
| T004 | Add a ratchet and fix source docstrings for the reduced `ui_api` surface | [tickets/T004.md](tickets/T004.md) |

<!-- TICKET_INDEX:END -->

## Work Breakdown (Tasks)

### T001: Migrate startup and model-selection flows off passthrough facades

**Summary**: Replace `core.ui_api` imports used by CLI startup, lifecycle, setup, model selection, theme switching, session deletion, and update flows with direct imports from the underlying `configuration`, `constants`, and `paths` modules.

**Owner**: ui-core

**Estimate**: 2.5h

**Dependencies**: none

**Target milestone**: M1

**Acceptance test**: `! rg -n "tunacode\.core\.ui_api\.(configuration|user_configuration|system_paths|constants)" src/tunacode/ui/main.py src/tunacode/ui/lifecycle.py src/tunacode/ui/screens/setup.py src/tunacode/ui/screens/model_picker.py src/tunacode/ui/screens/api_key_entry.py src/tunacode/ui/commands/model.py src/tunacode/ui/commands/theme.py src/tunacode/ui/commands/update.py src/tunacode/ui/commands/resume.py`

**Files/modules touched**:
- src/tunacode/ui/main.py
- src/tunacode/ui/lifecycle.py
- src/tunacode/ui/screens/setup.py
- src/tunacode/ui/screens/model_picker.py
- src/tunacode/ui/screens/api_key_entry.py
- src/tunacode/ui/commands/model.py
- src/tunacode/ui/commands/theme.py
- src/tunacode/ui/commands/update.py
- src/tunacode/ui/commands/resume.py

**Steps**:
1. In each listed file, replace `tunacode.core.ui_api.configuration` imports with direct imports from the specific source modules: `tunacode.configuration.defaults`, `tunacode.configuration.models`, `tunacode.configuration.pricing`, and `tunacode.configuration.settings`.
2. Replace `tunacode.core.ui_api.user_configuration` imports with direct imports from `tunacode.configuration.user_config`.
3. Replace `tunacode.core.ui_api.system_paths` imports with direct imports from `tunacode.configuration.paths`.
4. Replace `tunacode.core.ui_api.constants` imports in the listed files with direct imports from `tunacode.constants`.
5. Preserve current import placement, object construction timing, behavior, and call ordering; only change import sources and any now-unneeded alias names.
6. Run the acceptance grep command and confirm the listed files no longer reference the four removable facade modules.

### T002: Migrate runtime and rendering flows off passthrough facades

**Summary**: Replace `core.ui_api` imports used by the main app runtime, callbacks, compact command, session preview, widgets, styles, welcome message, and tool renderers with direct imports from `tunacode.constants`, `tunacode.types`, and `tunacode.utils.messaging`.

**Owner**: ui-core

**Estimate**: 3h

**Dependencies**: T001

**Target milestone**: M2

**Acceptance test**: `! rg -n "tunacode\.core\.ui_api\.(constants|shared_types|messaging)" src/tunacode/ui/app.py src/tunacode/ui/repl_support.py src/tunacode/ui/commands/clear.py src/tunacode/ui/commands/compact.py src/tunacode/ui/screens/session_picker.py src/tunacode/ui/widgets/messages.py src/tunacode/ui/widgets/resource_bar.py src/tunacode/ui/styles.py src/tunacode/ui/welcome.py src/tunacode/ui/renderers/agent_response.py src/tunacode/ui/renderers/panel_widths.py src/tunacode/ui/renderers/panels.py src/tunacode/ui/renderers/search.py src/tunacode/ui/renderers/tools/base.py src/tunacode/ui/renderers/tools/bash.py src/tunacode/ui/renderers/tools/diagnostics.py src/tunacode/ui/renderers/tools/discover.py src/tunacode/ui/renderers/tools/hashline_edit.py src/tunacode/ui/renderers/tools/read_file.py src/tunacode/ui/renderers/tools/web_fetch.py src/tunacode/ui/renderers/tools/write_file.py`

**Files/modules touched**:
- src/tunacode/ui/app.py
- src/tunacode/ui/repl_support.py
- src/tunacode/ui/commands/clear.py
- src/tunacode/ui/commands/compact.py
- src/tunacode/ui/screens/session_picker.py
- src/tunacode/ui/widgets/messages.py
- src/tunacode/ui/widgets/resource_bar.py
- src/tunacode/ui/styles.py
- src/tunacode/ui/welcome.py
- src/tunacode/ui/renderers/agent_response.py
- src/tunacode/ui/renderers/panel_widths.py
- src/tunacode/ui/renderers/panels.py
- src/tunacode/ui/renderers/search.py
- src/tunacode/ui/renderers/tools/base.py
- src/tunacode/ui/renderers/tools/bash.py
- src/tunacode/ui/renderers/tools/diagnostics.py
- src/tunacode/ui/renderers/tools/discover.py
- src/tunacode/ui/renderers/tools/hashline_edit.py
- src/tunacode/ui/renderers/tools/read_file.py
- src/tunacode/ui/renderers/tools/web_fetch.py
- src/tunacode/ui/renderers/tools/write_file.py

**Steps**:
1. Replace `tunacode.core.ui_api.constants` imports with direct imports from `tunacode.constants` in every listed runtime/rendering file.
2. Replace `tunacode.core.ui_api.shared_types` imports with direct imports from `tunacode.types` only; keep semantic casts such as `ModelName(model_name)` intact and do not substitute the unrelated `tunacode.constants.ToolName` enum.
3. Replace `tunacode.core.ui_api.messaging` imports with direct imports from `tunacode.utils.messaging`.
4. Keep `tunacode.core.ui_api.formatting` and `tunacode.core.ui_api.lsp_status` imports unchanged in this task because those modules still add adapter behavior.
5. Keep symbol-level imports and existing lazy-import placement unless a mechanical import-order fix is required by the existing architecture tests.
6. Run the acceptance grep command and confirm the listed files no longer reference the three removable runtime facade modules.

### T003: Delete dead facade modules and narrow the `core/ui_api` package surface

**Summary**: Remove the passthrough modules after all in-repo source callers stop using them, leaving `core/ui_api` with only the surviving behaviorful adapters.

**Owner**: core

**Estimate**: 1.5h

**Dependencies**: T002

**Target milestone**: M3

**Acceptance test**: `! rg -n "tunacode\.core\.ui_api\.(configuration|constants|messaging|shared_types|system_paths|user_configuration)" src/tunacode -g '*.py' && test "$(find src/tunacode/core/ui_api -maxdepth 1 -type f | xargs -n1 basename | sort | tr '\n' ' ')" = "__init__.py file_filter.py formatting.py lsp_status.py "`

**Files/modules touched**:
- src/tunacode/core/ui_api/configuration.py
- src/tunacode/core/ui_api/constants.py
- src/tunacode/core/ui_api/messaging.py
- src/tunacode/core/ui_api/shared_types.py
- src/tunacode/core/ui_api/system_paths.py
- src/tunacode/core/ui_api/user_configuration.py

**Steps**:
1. Delete `configuration.py`, `constants.py`, `messaging.py`, `shared_types.py`, `system_paths.py`, and `user_configuration.py` from `src/tunacode/core/ui_api/` with no compatibility shims.
2. Re-run a repository-wide grep over `src/tunacode/**/*.py` and confirm only `file_filter`, `formatting`, and `lsp_status` remain under `tunacode.core.ui_api`.
3. Run the acceptance shell test and confirm the package file set matches the expected reduced surface exactly.

### T004: Add a ratchet and fix source docstrings for the reduced `ui_api` surface

**Summary**: Add one architecture test that locks the reduced `core/ui_api` file set, and update only the now-false source docstrings/comments in surviving `core/ui_api` modules.

**Owner**: architecture

**Estimate**: 2h

**Dependencies**: T003

**Target milestone**: M4

**Acceptance test**: `uv run pytest tests/architecture/test_ui_api_surface.py tests/test_dependency_layers.py tests/architecture/test_layer_dependencies.py tests/architecture/test_import_order.py tests/architecture/test_init_bloat.py -q`

**Files/modules touched**:
- tests/architecture/test_ui_api_surface.py
- src/tunacode/core/ui_api/__init__.py
- src/tunacode/core/ui_api/file_filter.py
- src/tunacode/core/ui_api/formatting.py
- src/tunacode/core/ui_api/lsp_status.py

**Steps**:
1. Add `tests/architecture/test_ui_api_surface.py` that asserts the file set under `src/tunacode/core/ui_api/` matches the intended reduced surface from T003.
2. Update `src/tunacode/core/ui_api/__init__.py` so it states that `core.ui_api` exists only for UI-specific adapters that add behavior or translation, and that UI should import canonical shared modules directly otherwise.
3. Adjust only the now-false wording in surviving adapter docstrings/comments (for example, change `file_filter.py` from a “facade” description to an “adapter/wrapper” description); do not edit Markdown docs, `AGENTS.md`, or generated structure artifacts in this PR.
4. Run the acceptance pytest command and confirm the reduced surface plus layer/import-order/`__init__`-bloat rules all pass together.

## Risks & Mitigations

- Import churn across many UI files can create noisy diffs.
  - Mitigation: keep the refactor import-only, grouped by task, and avoid unrelated formatting changes.
- Some files currently rely on lazy imports to reduce startup cost or avoid cycles.
  - Mitigation: preserve lazy-import placement unless a direct top-level import is already used safely in a nearby file.
- Broader Markdown docs and generated artifacts will intentionally lag until the follow-up docs PR lands.
  - Mitigation: limit this PR to source docstrings/comments, and keep the deferred docs work explicitly out of scope in T004.
- A deleted facade could still be referenced outside `src/tunacode/ui/`.
  - Mitigation: repository-wide grep in T003 before deleting files permanently.
- A pre-existing pre-push hook failure on `ui/headless` could block artifact publication even if the refactor itself is correct.
  - Mitigation: keep the implementation scoped to `ui_api` reduction and surface the hook failure separately rather than coupling it to code cleanup in this plan.

## Test Strategy

- T001/T002 rely on grep-based proof that targeted files no longer import the removable facades.
- T003 relies on an exact filesystem assertion for the remaining `core/ui_api` file set.
- T004 adds one architecture ratchet test and reruns the existing dependency/layer/import-order/`__init__`-bloat suite.
- Do not add more than one new test file; the only new test should be `tests/architecture/test_ui_api_surface.py`.
- Broader doc-freshness and tree-generation checks are intentionally deferred to the follow-up docs PR.

## References

- Research doc: `.artifacts/research/2026-03-31_16-51-07_ui-api.md` — sections `Key Files`, `Data Ingress`, `Dependencies`, `Flow Maps`
- `src/tunacode/core/ui_api/configuration.py:1-101`
- `src/tunacode/core/ui_api/constants.py:1-47`
- `src/tunacode/core/ui_api/messaging.py:1-36`
- `src/tunacode/core/ui_api/shared_types.py:1-17`
- `src/tunacode/core/ui_api/system_paths.py:1-44`
- `src/tunacode/core/ui_api/user_configuration.py:1-51`
- `tests/test_dependency_layers.py:11-34`
- `docs/modules/utils/utils.md:1-23`
- `docs/modules/core/core.md:68-70`
- `src/tunacode/ui/main.py:10-12`
- `src/tunacode/ui/app.py:28-29,339,522,656,748`
- `src/tunacode/ui/commands/model.py:7,31,58-59,107-108,135`

## Final Gate

- **Output summary**: `.artifacts/plan/2026-03-31_17-00-48_ui-api-passthrough-reduction/`, 4 milestones, 4 tickets
- **Next step**: proceed to execute-phase with `.artifacts/plan/2026-03-31_17-00-48_ui-api-passthrough-reduction/PLAN.md`
