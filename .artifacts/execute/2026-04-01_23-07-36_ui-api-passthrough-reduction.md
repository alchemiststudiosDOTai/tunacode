---
title: "ui-api-passthrough-reduction execution log"
link: "ui-api-passthrough-reduction-execute"
type: debug_history
ontological_relations:
  - relates_to: [[ui-api-passthrough-reduction-plan]]
tags: [execute, ui-api-passthrough-reduction]
uuid: "6ea8a7eb-3492-47c7-9337-25e142186714"
created_at: "2026-04-01T23:07:41Z"
owner: "fabian"
plan_path: ".artifacts/plan/2026-03-31_17-00-48_ui-api-passthrough-reduction/PLAN.md"
start_commit: "27b7835e"
end_commit: "2ee4337d"
env: {target: "local", notes: "Plan refreshed locally before execution; existing ui/headless empty-dir pre-push blocker remains out of scope unless encountered again."}
---

## Pre-Flight Checks
- Branch: feat/ui-api-passthrough-reduction
- Rollback: 0ee762fa
- DoR: satisfied
- Access/secrets: present
- Fixtures/data: ready
- Ready: yes

## Task Execution

### T001 – Migrate startup and model-selection flows off passthrough facades
- Status: completed
- Commit: 23d230e7
- Files: src/tunacode/ui/main.py, src/tunacode/ui/lifecycle.py, src/tunacode/ui/screens/setup.py, src/tunacode/ui/screens/model_picker.py, src/tunacode/ui/screens/api_key_entry.py, src/tunacode/ui/commands/model.py, src/tunacode/ui/commands/theme.py, src/tunacode/ui/commands/update.py, src/tunacode/ui/commands/resume.py
- Commands: `rg -n "tunacode\.core\.ui_api\.(configuration|user_configuration|system_paths|constants)" ...` → identified targeted imports; `! rg -n "tunacode\.core\.ui_api\.(configuration|user_configuration|system_paths|constants)" ...` → pass
- Tests: acceptance grep passed
- Coverage delta: not measured
- Notes: Replaced passthrough imports with direct imports from configuration/defaults/models/settings/user_config/paths and tunacode.constants while preserving lazy imports and call ordering. `src/tunacode/ui/commands/update.py` now imports `configuration.paths._get_installed_version` under the existing local alias to avoid changing behavior.

### T002 – Migrate runtime and rendering flows off passthrough facades
- Status: completed
- Commit: 981f7df9
- Files: src/tunacode/ui/app.py, src/tunacode/ui/repl_support.py, src/tunacode/ui/commands/clear.py, src/tunacode/ui/commands/compact.py, src/tunacode/ui/screens/session_picker.py, src/tunacode/ui/widgets/messages.py, src/tunacode/ui/widgets/resource_bar.py, src/tunacode/ui/styles.py, src/tunacode/ui/welcome.py, src/tunacode/ui/renderers/agent_response.py, src/tunacode/ui/renderers/panel_widths.py, src/tunacode/ui/renderers/panels.py, src/tunacode/ui/renderers/search.py, src/tunacode/ui/renderers/tools/base.py, src/tunacode/ui/renderers/tools/bash.py, src/tunacode/ui/renderers/tools/diagnostics.py, src/tunacode/ui/renderers/tools/discover.py, src/tunacode/ui/renderers/tools/hashline_edit.py, src/tunacode/ui/renderers/tools/read_file.py, src/tunacode/ui/renderers/tools/web_fetch.py, src/tunacode/ui/renderers/tools/write_file.py
- Commands: `rg -n "tunacode\.core\.ui_api\.(constants|shared_types|messaging)" ...` → identified runtime/rendering passthrough imports; `! rg -n "tunacode\.core\.ui_api\.(constants|shared_types|messaging)" ...` → pass
- Tests: acceptance grep passed
- Coverage delta: not measured
- Notes: Replaced UI runtime/rendering imports with direct imports from `tunacode.constants`, `tunacode.types`, and `tunacode.utils.messaging`. Kept `core.ui_api.formatting` and `core.ui_api.lsp_status` imports unchanged per plan.

### T003 – Delete dead facade modules and narrow the `core/ui_api` package surface
- Status: completed
- Commit: bf1ca25c
- Files: src/tunacode/core/ui_api/configuration.py, src/tunacode/core/ui_api/constants.py, src/tunacode/core/ui_api/messaging.py, src/tunacode/core/ui_api/shared_types.py, src/tunacode/core/ui_api/system_paths.py, src/tunacode/core/ui_api/user_configuration.py
- Commands: `rg -n "tunacode\.core\.ui_api\.(configuration|constants|messaging|shared_types|system_paths|user_configuration)" src/tunacode -g '*.py'` → no matches; `rm ... && ! rg ... && test "$(find src/tunacode/core/ui_api ...)" = "__init__.py file_filter.py formatting.py lsp_status.py "` → pass
- Tests: repository-wide grep and reduced-surface shell test passed
- Coverage delta: not measured
- Notes: Deleted the six passthrough-only facade modules without shims after verifying no in-repo Python source still imports them. The first commit attempt was blocked by the repo-wide unused-constants hook because `RICHLOG_CLASS_PAUSED` became dead after the import migration; removed that constant as a trivial local lint fix before retrying.

### T004 – Add a ratchet and fix source docstrings for the reduced `ui_api` surface
- Status: completed
- Commit: 2ee4337d
- Files: tests/architecture/test_ui_api_surface.py, src/tunacode/core/ui_api/__init__.py, src/tunacode/core/ui_api/file_filter.py, src/tunacode/core/ui_api/lsp_status.py
- Commands: `uv run pytest tests/architecture/test_ui_api_surface.py tests/test_dependency_layers.py tests/architecture/test_layer_dependencies.py tests/architecture/test_import_order.py tests/architecture/test_init_bloat.py -q` → 70 passed in 0.27s
- Tests: acceptance pytest suite passed
- Coverage delta: not measured
- Notes: Added a filesystem ratchet for the reduced `core.ui_api` surface and updated surviving adapter docstrings to describe adapter behavior instead of the old facade contract.

## Gate Results
- Tests: `uv run pytest tests/architecture/test_ui_api_surface.py tests/test_dependency_layers.py tests/architecture/test_layer_dependencies.py tests/architecture/test_import_order.py tests/architecture/test_init_bloat.py -q` → pass (70 passed)
- Coverage: not run (not specified by plan)
- Type checks: not run (not specified by plan)
- Security: changed-file hooks passed during T001–T003 commits
- Linters: changed-file hooks passed during T001–T003 commits

## Deployment (if applicable)
- Staging: not applicable
- Prod: not applicable
- Timestamps: not applicable

## Issues & Resolutions
- T001 – Initial commit attempt failed because `ruff` reordered imports in three touched files → staged hook-generated import-order fixes and retried successfully.
- T002 – Initial commit attempt failed because `ruff` reordered imports and `vulture-changed` flagged an unused `args` parameter in `ui/commands/clear.py` → staged the formatting changes, renamed the parameter to `_args`, and retried successfully.
- T003 – Initial commit attempt failed because the repo-wide unused-constants hook flagged `RICHLOG_CLASS_PAUSED` after import migration removed its last use → removed the dead constant as a trivial local lint fix and retried successfully.

## Success Criteria
- [x] All planned gates passed
- [x] Rollout completed or rolled back
- [x] KPIs/SLOs within thresholds
- [x] Execution log saved

## Next Steps
- QA from execute using `.artifacts/execute/2026-04-01_23-07-36_ui-api-passthrough-reduction.md`.
