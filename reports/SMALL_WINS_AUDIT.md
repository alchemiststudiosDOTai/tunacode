# Small Wins Audit Report

**Date:** 2026-02-16
**Branch:** master @ b249ef37
**Scope:** Read-only detection and documentation. No edits performed.

---

## 1. Executive Summary (Top Quick Wins)

1. **Delete 10 empty orphaned directories** -- XS effort, L impact (reduces confusion)
2. **Fix 15 mypy type errors across 6 files** -- S effort, M impact (unblocks stricter type gates)
3. **Reduce complexity in 21 functions rated C+ by radon** -- S effort per function, M impact
4. **Remove `render_diff_tool` (dead method, only defined never called)** -- XS effort, S impact
5. **Remove `file_search_panel`, `code_search_panel`, `quick_results` (exported but never imported)** -- XS effort, S impact
6. **Fix 2 layer violations: configuration importing infrastructure** -- S effort, L impact
7. **Add module docstrings to 17 files (100% of infrastructure layer undocumented)** -- S effort, M impact

---

## 2. Findings by Category

### A. Structure & Naming

#### Empty/Orphaned Directories (10 items -- safe to delete)

No imports reference any of these. All contain only `__pycache__` or nothing.

| Directory | Notes |
|-----------|-------|
| `src/tunacode/lsp/` | Empty duplicate of `tools/lsp/` |
| `src/tunacode/indexing/` | Empty, unused |
| `src/tunacode/utils/config/` | Empty, unused |
| `src/tunacode/utils/parsing/` | Empty, unused |
| `src/tunacode/utils/ui/` | Empty duplicate of `ui/` |
| `src/tunacode/tools/authorization/` | Empty, unused |
| `src/tunacode/tools/parsing/` | Empty, unused |
| `src/tunacode/tools/messaging/` | Empty duplicate of `utils/messaging/` |
| `src/tunacode/core/prompting/` | Empty, unused |
| `src/tunacode/ui/tamagochi/` | Legacy name, replaced by `slopgotchi/` |

**Naming conventions:** All source files follow snake_case. No violations detected.

#### Stale dist artifacts
`dist/` contains old wheel files (`0.1.38`, `0.1.41`) while current version is `0.1.65`. Consider cleaning.

---

### B. Dead Code & Orphans

#### Unused Exported Symbols (DONE -- removed in batch 1)

| Symbol | File | Status |
|--------|------|--------|
| `render_diff_tool()` | `ui/renderers/panels.py:176` | REMOVED |
| `file_search_panel()` | `ui/renderers/search.py:285` | REMOVED |
| `code_search_panel()` | `ui/renderers/search.py:298` | REMOVED |
| `quick_results()` | `ui/renderers/search.py:311` | REMOVED |
| `tool_panel()` | `ui/renderers/panels.py:423` | Only called by `tool_panel_smart` (internal) |
| `error_panel()` | `ui/renderers/panels.py:443` | Exported in `__init__`, verify usage |
| `search_panel()` | `ui/renderers/panels.py:460` | Exported in `__init__`, verify usage |

#### Entirely Unreferenced Files (never imported anywhere)

| File | Lines | Contents |
|------|-------|----------|
| `core/agents/agent_components/state_transition.py` | ~120 | `AgentStateMachine`, `StateTransitionRules` -- entire file dead |
| `core/agents/agent_components/openai_response_validation.py` | ~265 | `validate_openai_chat_completion_response()` + helpers -- entire file dead |
| `ui/renderers/panel_widths.py` | 15 | `tool_panel_frame_width()` -- never used |

#### Unused Exception Classes (defined, never raised or caught)

| Exception | File:Line | Notes |
|-----------|-----------|-------|
| `StateError` | `exceptions.py:185` | Only in error style map |
| `GitOperationError` | `exceptions.py:198` | Only in error style/fix maps |
| `ServiceError` | `exceptions.py:192` | Only parent of GitOperationError |
| `SetupValidationError` | `exceptions.py:243` | Only in error style map |
| `ModelConfigurationError` | `exceptions.py:224` | Only in error style/fix maps |
| `ToolBatchingJSONError` | `exceptions.py:308` | Only in error style map |
| `AggregateToolError` | `exceptions.py:349` | Never imported or raised |

#### Unused Functions/Methods

| Symbol | Location | Notes |
|--------|----------|-------|
| `render_info()` | `ui/renderers/panels.py:344` | Never called |
| `render_success()` | `ui/renderers/panels.py:358` | Never called |
| `render_warning()` | `ui/renderers/panels.py:369` | Never called |
| `calculate_cost()` | `configuration/pricing.py:42` | Never imported |
| `from_canonical_list()` | `utils/messaging/adapter.py:399` | Exported, never imported |
| `get_readable_tool_description()` | `core/agents/agent_components/agent_helpers.py:67` | Never called |
| `_describe_research()` | `core/agents/agent_components/agent_helpers.py:37` | Maps to nonexistent `research_codebase` tool |

#### Unused Dataclasses/Types

| Symbol | Location | Notes |
|--------|----------|-------|
| `ResponseState` | `core/types/agent_state.py:8` | Exported, never imported |
| `TokenUsage` | `types/dataclasses.py:29` | Exported, never imported |
| `CostBreakdown` | `types/dataclasses.py:38` | Exported, never imported |
| `ModelConfig` | `types/dataclasses.py:19` | Exported, never imported (registry uses raw dicts) |
| `RecursiveContext` | `types/canonical.py:297` | Exported, never imported |

#### TODO/FIXME Debt
**Zero items.** The codebase has no TODO, FIXME, HACK, XXX, or WORKAROUND comments.

#### Vulture Dead Code
**Zero findings** at 80% confidence threshold. Clean.

---

### C. Lint & Config Drifts

#### Ruff: CLEAN
All checks passed. No violations.

#### Mypy: 15 errors in 6 files

| File | Count | Error Type |
|------|-------|------------|
| `tools/utils/text_match.py:376` | 1 | Missing return statement |
| `tools/utils/ripgrep.py:245` | 1 | Module has no attribute "SubprocessError" |
| `constants.py:326` | 5 | Incompatible type for Theme constructor |
| `ui/widgets/editor.py:292,298,301` | 3 | Incompatible type for Text.stylize |
| `tools/web_fetch.py:229` | 1 | Missing return statement |
| `ui/shell_runner.py:168` | 1 | Incompatible return value type |
| `core/compaction/controller.py:257,273,287` | 3 | str vs Literal type mismatch |

**Note:** CLAUDE.md states "50 errors in 17 files" as of 2026-01-27. Down to 15 errors in 6 files -- significant progress.

#### Radon Complexity: 21 functions at C+ (complexity >= 11)

| Function | File | Complexity |
|----------|------|-----------|
| `WebFetchRenderer._detect_content_type` | `ui/renderers/tools/web_fetch.py:103` | C (16) |
| `FileFilter.fast_glob` | `tools/grep_components/file_filter.py:21` | C (15) |
| `SearchDisplayRenderer.parse_glob_output` | `ui/renderers/search.py:229` | C (15) |
| `GrepRenderer.parse_result` | `ui/renderers/tools/grep.py:44` | C (15) |
| `SelectableRichVisual` (class) | `ui/widgets/chat.py:33` | C (15) |
| `SelectableRichVisual.render_strips` | `ui/widgets/chat.py:44` | C (14) |
| `UpdateFileRenderer._parse_side_by_side_rows` | `ui/renderers/tools/update_file.py:144` | C (14) |
| `bash` | `tools/bash.py:20` | C (13) |
| `_expand_brace_pattern` | `tools/glob.py:112` | C (13) |
| `render_diagnostics_inline` | `ui/renderers/tools/diagnostics.py:106` | C (13) |
| `list_cwd` | `utils/system/gitignore.py:35` | F (12) |
| `_collect_files` | `tools/list_dir.py:21` | C (11) |
| `ParallelGrep._ripgrep_search_filtered` | `tools/grep.py:242` | C (11) |
| `ParallelGrep._hybrid_search_filtered` | `tools/grep.py:372` | C (11) |
| `LSPClient._read_messages` | `tools/lsp/client.py:180` | C (11) |
| `PatternMatcher.search_file` | `tools/grep_components/pattern_matcher.py:36` | C (11) |
| `parse_diagnostics_block` | `ui/renderers/tools/diagnostics.py:39` | C (11) |
| `UpdateFileRenderer.parse_result` | `ui/renderers/tools/update_file.py:74` | C (11) |
| `Editor.on_key` | `ui/widgets/editor.py:78` | C (11) |
| `_filter_assistant_tool_calls` | `core/agents/resume/sanitize.py:116` | C (11) |
| `log_message_history_debug` | `core/agents/resume/sanitize_debug.py:57` | C (11) |
| `FileFilter.complete` | `infrastructure/file_filter.py:129` | C (11) |

**pyproject.toml sets max-complexity = 10.** All 21 functions exceed this threshold.

#### Config Drift

- Ruff excludes `vulture_whitelist.py` and `.osgrep/` which don't exist (preventive, harmless)
- `docs/agent-docs/` referenced in CLAUDE.md doesn't exist as a directory
- No `.editorconfig`, `ruff.toml`, or `mypy.ini` -- all config centralized in `pyproject.toml` (good)

---

### D. Test Coverage Gaps

**135 source modules, ~40 test files (30.4% module coverage)**

| Layer | Tested | Total | Coverage |
|-------|--------|-------|----------|
| configuration | 0 | 9 | 0.0% |
| constants | 0 | 1 | 0.0% |
| infrastructure | 0 | 8 | 0.0% |
| core | 6 | 31 | 19.4% |
| tools | 8 | 25 | 32.0% |
| ui | 22 | 53 | 41.5% |
| types | 2 | 4 | 50.0% |
| utils | 2 | 3 | 66.7% |
| exceptions | 1 | 1 | 100.0% |

**Biggest gaps:** configuration (0%), infrastructure (0%), core (19.4%).

---

### E. Architecture Issues

#### Layer Violations (2 files)

| File | Violation |
|------|-----------|
| `configuration/limits.py` | Imports `tunacode.infrastructure.cache.caches` |
| `configuration/models.py` | Imports `tunacode.infrastructure.cache.caches` |

Configuration (shared layer) should not depend on infrastructure. This inverts the dependency hierarchy.

#### Largest Files (>400 lines)

| File | Lines |
|------|-------|
| `core/agents/main.py` | 588 |
| `ui/app.py` | 580 |
| `ui/renderers/panels.py` | 528 |
| `core/compaction/controller.py` | 522 |
| `tools/grep.py` | 479 |
| `ui/renderers/tools/base.py` | 476 |
| `utils/messaging/adapter.py` | 457 |
| `ui/renderers/tools/update_file.py` | 442 |
| `tools/utils/text_match.py` | 424 |
| `ui/widgets/editor.py` | 402 |

#### High Fan-In Imports

`ui/app.py` imports from 17+ distinct modules -- highest in the codebase. Expected for an application entry point but worth monitoring.

---

## 3. Per-File Suggestions (No Edits)

| Path | Issue | Suggested Action | Effort | Risk |
|------|-------|-----------------|--------|------|
| `src/tunacode/lsp/` | Empty directory | Delete | XS | None |
| `src/tunacode/indexing/` | Empty directory | Delete | XS | None |
| `src/tunacode/utils/config/` | Empty directory | Delete | XS | None |
| `src/tunacode/utils/parsing/` | Empty directory | Delete | XS | None |
| `src/tunacode/utils/ui/` | Empty directory | Delete | XS | None |
| `src/tunacode/tools/authorization/` | Empty directory | Delete | XS | None |
| `src/tunacode/tools/parsing/` | Empty directory | Delete | XS | None |
| `src/tunacode/tools/messaging/` | Empty directory | Delete | XS | None |
| `src/tunacode/core/prompting/` | Empty directory | Delete | XS | None |
| `src/tunacode/ui/tamagochi/` | Legacy empty dir | Delete | XS | None |
| `ui/renderers/panels.py:176` | `render_diff_tool` unused | Delete method | XS | Low |
| `ui/renderers/search.py:285` | `file_search_panel` unused | Delete function | XS | Low |
| `ui/renderers/search.py:298` | `code_search_panel` unused | Delete function | XS | Low |
| `ui/renderers/search.py:311` | `quick_results` unused | Delete function | XS | Low |
| `ui/renderers/__init__.py` | Exports dead symbols | Remove from `__all__` | XS | Low |
| `tools/utils/text_match.py:376` | Missing return | Add return statement | XS | Low |
| `tools/web_fetch.py:229` | Missing return | Add return statement | XS | Low |
| `tools/utils/ripgrep.py:245` | Wrong attribute | Fix SubprocessError ref | XS | Low |
| `constants.py:326` | Theme constructor types | Fix dict unpacking types | S | Low |
| `ui/widgets/editor.py:292` | stylize type mismatch | Cast or fix style type | XS | Low |
| `ui/shell_runner.py:168` | Return type mismatch | Fix return annotation | XS | Low |
| `core/compaction/controller.py:257` | str vs Literal | Use literal values | XS | Low |
| `configuration/limits.py` | Layer violation | Move cache access up | S | Med |
| `configuration/models.py` | Layer violation | Move cache access up | S | Med |
| `tools/grep_components/file_filter.py:21` | Complexity 15 | Extract helper functions | S | Low |
| `ui/renderers/tools/web_fetch.py:103` | Complexity 16 | Extract content type map | S | Low |
| `dist/` | Stale wheel artifacts | Clean old builds | XS | None |

---

## 4. Guardrails & Next Steps

### Batch Plan (<=30 min PRs, <=10 files/PR)

**PR 1: Delete empty directories (XS, 5 min)**
- Remove all 10 empty directories listed above
- Verify no import breakage with `uv run pytest`

**PR 2: Remove dead exported symbols (XS, 10 min)**
- Delete `render_diff_tool`, `file_search_panel`, `code_search_panel`, `quick_results`
- Update `ui/renderers/__init__.py` exports
- Run tests to confirm no breakage

**PR 3: Fix mypy errors (S, 20 min)**
- Fix 15 type errors across 6 files
- Verify with `uv run mypy src/tunacode/`

**PR 4: Clean stale dist artifacts (XS, 2 min)**
- Remove old wheel files from `dist/`

**PR 5: Fix layer violations (S, 30 min)**
- Refactor `configuration/limits.py` and `configuration/models.py`
- Move infrastructure imports to a higher layer
- Run architecture tests

**PR 6: Reduce top-5 complexity functions (S, 30 min each)**
- Target functions with complexity >= 14 first
- Extract helper functions, use early returns

### Testing Rules
- Every deletion PR must pass `uv run pytest`
- Every refactor PR must pass `uv run ruff check . && uv run mypy src/tunacode/`
- Add tests where deletion occurs (per CLAUDE.md guidelines)
