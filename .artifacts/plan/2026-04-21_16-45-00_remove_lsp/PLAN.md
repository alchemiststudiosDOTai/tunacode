---
title: "Remove LSP subsystem implementation plan"
link: "remove-lsp-plan"
type: implementation_plan
ontological_relations:
  - relates_to: [[lsp-research]]
tags: [plan, lsp, removal]
uuid: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
created_at: "2026-04-21T16:45:00-05:00"
parent_research: ".artifacts/research/2026-04-21_16-31-56_lsp.md"
git_commit_at_plan: "bf832160"
---

## Goal

Complete excision of the LSP (Language Server Protocol) subsystem from tunacode-cli. Remove all source code, type definitions, configuration defaults, validation logic, UI status rendering, diagnostics rendering, tool integrations, tests, and documentation references. After this change, the codebase contains zero LSP-related code paths.

## Scope & Assumptions

- **IN scope:**
  - Deleting `src/tunacode/tools/lsp/` package (4 Python files + `__pycache__`)
  - Deleting `src/tunacode/core/ui_api/lsp_status.py`
  - Deleting `src/tunacode/ui/renderers/tools/diagnostics.py` (LSP-specific renderer)
  - Removing LSP imports and calls from `hashline_edit.py` and `write_file.py`
  - Removing LSP status from `app.py` and `resource_bar.py`
  - Removing LSP diagnostics parsing/rendering from `hashline_edit.py` renderer
  - Removing `LspSettings` from `types/base.py` and `types/__init__.py`
  - Removing `lsp` block from `configuration/defaults.py` and `configuration/user_config.py`
  - Removing LSP constants from `ui/repl_support.py`
  - Updating architecture tests (`test_dependency_layers.py`, `test_import_order.py`, `test_init_bloat.py`, `test_ui_api_surface.py`)
  - Updating unit/system tests (`test_user_config_loading.py`, `test_repl_support.py`, `test_request_threading.py`)
  - Updating `pyproject.toml` (remove `tunacode.lsp*` from ignore list)
  - Updating `scripts/preview_tool_panels.py`
  - Updating docs (`README.md`, `AGENTS.md`, `docs/modules/tools/*.md`, `docs/modules/ui/ui.md`, `docs/modules/configuration/configuration.md`)

- **OUT of scope:**
  - Refactoring unrelated tool logic
  - Adding replacement diagnostics features
  - CI/CD workflow changes (except docs consistency)
  - Deprecation warnings or migration logic for user configs that already contain `lsp` keys (the dict merge in `load_config` tolerates extra keys)

- **Assumptions:**
  - No other code outside the identified blast radius imports from `tunacode.tools.lsp` or `tunacode.core.ui_api.lsp_status`
  - `UserConfig` dict merge in `load_config` gracefully ignores unknown keys, so persisted configs with `lsp` won't crash
  - The diagnostics renderer (`diagnostics.py`) is only consumed by the hashline_edit renderer and has no standalone usage

## Deliverables

- Source tree with `src/tunacode/tools/lsp/` and `src/tunacode/core/ui_api/lsp_status.py` deleted
- Clean imports in `hashline_edit.py`, `write_file.py`, `app.py`, `resource_bar.py`, `hashline_edit.py` renderer, `repl_support.py`
- Updated type system (`UserSettings` no longer contains `lsp` key)
- Updated configuration defaults and validation
- Updated architecture and unit tests (all green)
- Updated documentation (no stale LSP references)

## Readiness

- Research artifact exists at `.artifacts/research/2026-04-21_16-31-56_lsp.md`
- Git working tree is clean at `bf832160`
- All LSP references have been enumerated via `grep -ri "lsp"`

## Milestones

- **M1:** Delete LSP source packages and UI adapters
- **M2:** Remove LSP wiring from tool layer (`hashline_edit`, `write_file`, diagnostics renderer)
- **M3:** Remove LSP wiring from UI layer (`app`, `resource_bar`, `repl_support`)
- **M4:** Remove LSP from types and configuration
- **M5:** Update all tests
- **M6:** Update docs and config metadata, run validation gates

## Ticket Index

<!-- TICKET_INDEX:START -->
- [T001](tickets/T001.md) — Delete LSP source packages and UI adapter
- [T002](tickets/T002.md) — Remove LSP wiring from hashline_edit and write_file tools
- [T003](tickets/T003.md) — Remove LSP diagnostics renderer and hashline_edit renderer references
- [T004](tickets/T004.md) — Remove LSP status from UI app and resource bar
- [T005](tickets/T005.md) — Remove LSP constants from repl_support.py
- [T006](tickets/T006.md) — Remove LspSettings from types and configuration
- [T007](tickets/T007.md) — Update architecture tests
- [T008](tickets/T008.md) — Update unit and system tests for config and UI behavior
- [T009](tickets/T009.md) — Update pyproject.toml and preview script
- [T010](tickets/T010.md) — Update documentation
- [T011](tickets/T011.md) — Run full validation gates
<!-- TICKET_INDEX:END -->

## Work Breakdown (Tasks)

### T001: Delete LSP source packages and UI adapter

**Summary**: Delete `src/tunacode/tools/lsp/` and `src/tunacode/core/ui_api/lsp_status.py`

**Owner**: backend

**Estimate**: 15m

**Dependencies**: <none>

**Target milestone**: M1

**Acceptance test**: `find src -path "*lsp*" -type f` returns only non-LSP files (e.g., models_registry.json false positives)

**Files/modules touched**:
- `src/tunacode/tools/lsp/__init__.py` (delete)
- `src/tunacode/tools/lsp/client.py` (delete)
- `src/tunacode/tools/lsp/servers.py` (delete)
- `src/tunacode/tools/lsp/diagnostics.py` (delete)
- `src/tunacode/core/ui_api/lsp_status.py` (delete)

**Steps**:
1. `rm -rf src/tunacode/tools/lsp/`
2. `rm src/tunacode/core/ui_api/lsp_status.py`

### T002: Remove LSP wiring from hashline_edit and write_file tools

**Summary**: Remove `maybe_prepend_lsp_diagnostics` import and call from both file tools so they return plain diff/text results.

**Owner**: backend

**Estimate**: 15m

**Dependencies**: T001

**Target milestone**: M2

**Acceptance test**: `grep -n "lsp" src/tunacode/tools/hashline_edit.py src/tunacode/tools/write_file.py` returns zero matches

**Files/modules touched**:
- `src/tunacode/tools/hashline_edit.py`
- `src/tunacode/tools/write_file.py`

**Steps**:
1. In `hashline_edit.py`, remove the import line `from tunacode.tools.lsp.diagnostics import maybe_prepend_lsp_diagnostics`
2. In `hashline_edit.py`, change `return await maybe_prepend_lsp_diagnostics(output, Path(filepath))` to `return output`
3. In `write_file.py`, remove the import line `from tunacode.tools.lsp.diagnostics import maybe_prepend_lsp_diagnostics`
4. In `write_file.py`, change `return await maybe_prepend_lsp_diagnostics(result, Path(filepath))` to `return result`

### T003: Remove LSP diagnostics renderer and hashline_edit renderer references

**Summary**: Delete the diagnostics renderer module and strip all diagnostics-block handling from the hashline_edit renderer.

**Owner**: backend

**Estimate**: 20m

**Dependencies**: T001

**Target milestone**: M2

**Acceptance test**: `grep -rn "diagnostics_block\|extract_diagnostics_from_result\|render_diagnostics_inline\|parse_diagnostics_block" src/tunacode/ui/renderers/` returns zero matches

**Files/modules touched**:
- `src/tunacode/ui/renderers/tools/diagnostics.py` (delete)
- `src/tunacode/ui/renderers/tools/hashline_edit.py`

**Steps**:
1. Delete `src/tunacode/ui/renderers/tools/diagnostics.py`
2. In `hashline_edit.py` renderer:
   - Remove `diagnostics_block: str | None = None` field from `EditDiffData`
   - Remove the `extract_diagnostics_from_result` import and call in `parse_result`
   - Remove `diagnostics_block=diagnostics_block` from the `EditDiffData` constructor call
   - Remove the entire diagnostics-zone block (lines ~397-412) from `render_result`
   - Update the docstring on `HashlineEditRenderer` to remove "with optional diagnostics zone"

### T004: Remove LSP status from UI app and resource bar

**Summary**: Remove `update_lsp_for_file` method from `TextualReplApp` and strip LSP fields/methods from `ResourceBar`.

**Owner**: backend

**Estimate**: 20m

**Dependencies**: T001

**Target milestone**: M3

**Acceptance test**: `grep -rn "lsp" src/tunacode/ui/app.py src/tunacode/ui/widgets/resource_bar.py` returns zero matches

**Files/modules touched**:
- `src/tunacode/ui/app.py`
- `src/tunacode/ui/widgets/resource_bar.py`

**Steps**:
1. In `app.py`, remove the `self.update_lsp_for_file(filepath)` call inside the tool-result handler
2. In `app.py`, delete the entire `update_lsp_for_file` method
3. In `resource_bar.py`:
   - Remove `self._lsp_server` and `self._lsp_available` from `__init__`
   - Remove `update_lsp_status` method
   - Remove the `if self._lsp_server:` block from `_refresh_display`
   - Update class docstring to remove "LSP server status"

### T005: Remove LSP constants from repl_support.py

**Summary**: Remove diagnostics block regex constants that were used solely for LSP diagnostics parsing.

**Owner**: backend

**Estimate**: 10m

**Dependencies**: T003

**Target milestone**: M3

**Acceptance test**: `grep -n "DIAGNOSTICS\|file_diagnostics" src/tunacode/ui/repl_support.py` returns zero matches

**Files/modules touched**:
- `src/tunacode/ui/repl_support.py`

**Steps**:
1. Remove `DIAGNOSTICS_BLOCK_START`, `DIAGNOSTICS_BLOCK_END`, `DIAGNOSTICS_BLOCK_PATTERN`, `DIAGNOSTICS_BLOCK_RE` definitions
2. In `build_tool_result_callback`, remove the `diagnostics_match = DIAGNOSTICS_BLOCK_RE.match(content)` block and the `if content.startswith(DIAGNOSTICS_BLOCK_START):` guard logic
3. Verify `repl_support.py` still passes its own tests after cleanup

### T006: Remove LspSettings from types and configuration

**Summary**: Excise `LspSettings` TypedDict and `lsp` field from `UserSettings`, defaults, and validation.

**Owner**: backend

**Estimate**: 20m

**Dependencies**: <none> (can be done in parallel with T001-T005, but safer after)

**Target milestone**: M4

**Acceptance test**: `grep -rn "LspSettings\|\"lsp\"" src/tunacode/types/ src/tunacode/configuration/` returns zero matches; `uv run pytest tests/unit/configuration/test_user_config_loading.py -v` passes

**Files/modules touched**:
- `src/tunacode/types/base.py`
- `src/tunacode/types/__init__.py`
- `src/tunacode/configuration/defaults.py`
- `src/tunacode/configuration/user_config.py`

**Steps**:
1. In `types/base.py`:
   - Delete `class LspSettings(TypedDict)`
   - Remove `"lsp": LspSettings` from `UserSettings`
2. In `types/__init__.py`:
   - Remove `LspSettings` from the `from tunacode.types.base import ...` re-export list
3. In `configuration/defaults.py`:
   - Remove the `"lsp": {"enabled": True, "timeout": 5.0}` block from `DEFAULT_USER_CONFIG["settings"]`
4. In `configuration/user_config.py`:
   - Remove `LspSettings` import
   - Delete `_validate_lsp_settings` function
   - Remove `lsp=_validate_lsp_settings(raw_settings["lsp"])` from `_validate_settings`

### T007: Update architecture tests

**Summary**: Remove LSP from layer models, import order lists, init bloat overrides, and UI API surface allowlists.

**Owner**: backend

**Estimate**: 15m

**Dependencies**: T001, T004

**Target milestone**: M5

**Acceptance test**: `uv run pytest tests/test_dependency_layers.py tests/architecture/test_import_order.py tests/architecture/test_init_bloat.py tests/architecture/test_ui_api_surface.py -v` passes

**Files/modules touched**:
- `tests/test_dependency_layers.py`
- `tests/architecture/test_import_order.py`
- `tests/architecture/test_init_bloat.py`
- `tests/architecture/test_ui_api_surface.py`

**Steps**:
1. In `test_dependency_layers.py`:
   - Remove `"lsp"` from `LAYERS`
   - Remove `"lsp": set()` from `ALLOWED_IMPORTS`
   - Remove `"tools": {"lsp"}` entry (or change to `"tools": set()`)
2. In `test_import_order.py`:
   - Remove `"lsp"` from `SHARED_LAYER_MODULES`
3. In `test_init_bloat.py`:
   - Remove `Path("tools/lsp/__init__.py"): 109` from `INIT_LINE_LIMIT_OVERRIDES`
4. In `test_ui_api_surface.py`:
   - Remove `"lsp_status.py"` from the allowlist

### T008: Update unit and system tests for config and UI behavior

**Summary**: Remove LSP test cases and mock methods from config loading tests, repl support tests, and request threading tests.

**Owner**: backend

**Estimate**: 20m

**Dependencies**: T004, T006

**Target milestone**: M5

**Acceptance test**: `uv run pytest tests/unit/configuration/test_user_config_loading.py tests/system/cli/test_repl_support.py tests/unit/ui/test_request_threading.py -v` passes

**Files/modules touched**:
- `tests/unit/configuration/test_user_config_loading.py`
- `tests/system/cli/test_repl_support.py`
- `tests/unit/ui/test_request_threading.py`

**Steps**:
1. In `test_user_config_loading.py`:
   - Remove `"lsp": {"enabled": False}` from the partial config fixture
   - Remove assertions for `loaded_config["settings"]["lsp"]["enabled"]` and `loaded_config["settings"]["lsp"]["timeout"]`
2. In `test_repl_support.py`:
   - Remove `self.updated_lsp_files` and `self.update_lsp_for_file` from the mock app fixture
   - Update `test_tool_result_callback_posts_message_for_completed_file_edit_without_lsp_update` to remove LSP-specific assertions (or rename and simplify)
3. In `test_request_threading.py`:
   - Remove `self.lsp_updates` and `self.update_lsp_for_file` from the mock app
   - Remove `test_tool_result_callback_never_calls_update_lsp_for_file_from_request_thread`
   - Remove `test_on_tool_result_display_updates_lsp_on_ui_thread_for_file_edits`

### T009: Update pyproject.toml and preview script

**Summary**: Remove LSP module from flake8/pylint ignore patterns and remove diagnostics sample from preview script.

**Owner**: backend

**Estimate**: 10m

**Dependencies**: T001

**Target milestone**: M6

**Acceptance test**: `grep -n "tunacode.lsp" pyproject.toml` returns zero matches; `grep -n "file_diagnostics" scripts/preview_tool_panels.py` returns zero matches

**Files/modules touched**:
- `pyproject.toml`
- `scripts/preview_tool_panels.py`

**Steps**:
1. In `pyproject.toml`, remove `"tunacode.lsp*"` from the ignore/exclude list (line ~163)
2. In `scripts/preview_tool_panels.py`:
   - Remove the `diagnostics` string block with `<file_diagnostics>` tags
   - Remove `with_diagnostics` parameter usage in `build_hashline_edit_result`

### T010: Update documentation

**Summary**: Strip all LSP references from README, AGENTS.md, and module docs so no stale documentation remains.

**Owner**: docs

**Estimate**: 20m

**Dependencies**: T001-T009

**Target milestone**: M6

**Acceptance test**: `grep -ri "lsp\|LSP" README.md AGENTS.md docs/modules/` returns zero matches (allowing false positives like "Meta-Llama" in models_registry.json which is in `docs/`)

**Files/modules touched**:
- `README.md`
- `AGENTS.md`
- `docs/modules/tools/tools.md`
- `docs/modules/tools/tools-system.md`
- `docs/modules/tools/hashline-subsystem.md`
- `docs/modules/ui/ui.md`
- `docs/modules/configuration/configuration.md`

**Steps**:
1. `README.md`:
   - Remove "LSP diagnostics" bullet from feature list
   - Remove the entire "LSP Integration" section
2. `AGENTS.md`:
   - Remove `src/tunacode/tools/lsp/` from the notable sub-packages list
3. `docs/modules/tools/tools.md`:
   - Remove `lsp/` row from the tools table (or update description)
   - Remove "prepends LSP diagnostics when available" from `hashline_edit` and `write_file` descriptions
4. `docs/modules/tools/tools-system.md`:
   - Remove `lsp/` from dependency diagram
   - Remove LSP-related bullet points
5. `docs/modules/tools/hashline-subsystem.md`:
   - Remove "Optional LSP diagnostics" bullet
   - Remove "Prepends LSP diagnostics when any are available" sentence
6. `docs/modules/ui/ui.md`:
   - Remove LSP server status from `resource_bar.py` description
   - Remove `render_diagnostics` LSP reference
7. `docs/modules/configuration/configuration.md`:
   - Remove mention of nested `lsp` settings from `defaults.py` description

### T011: Run full validation gates

**Summary**: Execute lint, architecture tests, unit tests, and dependency layer checks to prove the removal is clean.

**Owner**: backend

**Estimate**: 15m

**Dependencies**: T001-T010

**Target milestone**: M6

**Acceptance test**: All of the following exit 0:
- `uv run pytest tests/test_dependency_layers.py -v`
- `uv run pytest tests/architecture/test_import_order.py -v`
- `uv run pytest tests/architecture/test_init_bloat.py -v`
- `uv run pytest tests/architecture/test_ui_api_surface.py -v`
- `uv run pytest tests/unit/configuration/test_user_config_loading.py -v`
- `uv run pytest tests/system/cli/test_repl_support.py -v`
- `uv run pytest tests/unit/ui/test_request_threading.py -v`
- `uv run pre-commit run --all-files` (or equivalent lint gate)

**Files/modules touched**:
- None (verification only)

**Steps**:
1. Run architecture tests
2. Run affected unit/system tests
3. Run lint/typecheck gates
4. Capture output as proof artifact

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Persisted user configs contain `"lsp"` key causing validation errors | `validate_user_config` only checks required keys; `UserSettings` TypedDict is structural, not nominal, in runtime. The `_merge_config_value` will keep the key but `_validate_settings` no longer references it. If `raw_settings["lsp"]` is accessed, it will KeyError. **Mitigation**: In T006, ensure `_validate_settings` does NOT reference `raw_settings["lsp"]` — it is removed. Extra keys in the merged dict are harmless because Python dicts allow extra keys even when passed to a TypedDict constructor if the constructor itself doesn't reference them. |
| `hashline_edit` renderer has hidden dependencies on `diagnostics.py` via dynamic import | The dynamic import is inside a conditional branch that only runs when `data.diagnostics_block` is truthy. Since the parser no longer populates that field, the import path is unreachable. **Mitigation**: Still delete `diagnostics.py` and remove the branch in T003. |
| `src/tunacode/tools/lsp/__pycache__` left behind | `rm -rf` the entire directory including `__pycache__` in T001. |
| Architecture test layer graph cached by grimp is stale | Run `uv run python scripts/grimp_layers_report.py` after removal if there is a regeneration target, or let CI handle it. |

## Test Strategy

- One architecture test per layer boundary (existing tests, updated in T007)
- One config loading test proving `lsp` key is no longer required (updated in T008)
- One UI test proving `update_lsp_for_file` callbacks are gone (updated in T008)
- Lint/typecheck as final gate (T011)

## References

- Research doc: `.artifacts/research/2026-04-21_16-31-56_lsp.md`
- LSP package: `src/tunacode/tools/lsp/`
- UI adapter: `src/tunacode/core/ui_api/lsp_status.py`
- Tool integration: `src/tunacode/tools/hashline_edit.py:27`, `src/tunacode/tools/write_file.py:22`
- UI renderers: `src/tunacode/ui/renderers/tools/diagnostics.py`, `src/tunacode/ui/renderers/tools/hashline_edit.py`
- Config/types: `src/tunacode/types/base.py:35-37`, `src/tunacode/configuration/defaults.py:23-41`, `src/tunacode/configuration/user_config.py:154-197`
- Tests: `tests/test_dependency_layers.py:10-19`, `tests/unit/configuration/test_user_config_loading.py:21-25`

## Final Gate

- **Output summary**: plan bundle written to `.artifacts/plan/2026-04-21_16-45-00_remove_lsp/`, 4 milestones, 11 tickets
- **Next step**: proceed to execute-phase with `.artifacts/plan/2026-04-21_16-45-00_remove_lsp/PLAN.md`
