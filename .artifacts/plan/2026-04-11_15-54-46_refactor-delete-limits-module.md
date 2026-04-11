---
title: "refactor: delete limits module implementation plan"
link: "delete-limits-module-plan"
type: implementation_plan
ontological_relations:
  - relates_to: [[limits-config-map-research]]
tags: [plan, limits, configuration, coding]
uuid: "37A48965-4B46-48A2-B008-CB3833EAB265"
created_at: "2026-04-11T15:54:46-0500"
parent_research: ".artifacts/research/2026-04-11_15-47-09_limits-config-map.md"
git_commit_at_plan: "27f85393"
---

## Goal

- Remove `src/tunacode/configuration/limits.py` and its duplicate config-loading/cache path.
- Rewire runtime consumers to use already-loaded typed state while preserving current behavior.

Out of scope:
- Changing the meaning of `settings.max_tokens`
- Changing the meaning of `session.conversation.max_tokens`
- Altering model registry context-window behavior
- Broad cache-system refactors outside the deleted limits-settings cache

## Scope & Assumptions

- In scope:
  - Delete the `limits.py` module and the `limits_settings` cache module
  - Route bash output truncation through typed runtime settings
  - Route optional stream `max_tokens` caps through typed runtime settings
  - Update tests and docs that name the deleted module
- Out of scope:
  - Changing user config schema in `src/tunacode/configuration/user_config.py`
  - Changing session startup/load behavior in `src/tunacode/core/session/state.py`
  - Reworking compaction thresholds, UI gauges, or model context-window calculations
- Assumptions:
  - `settings.max_command_output` remains a user-configured bash output truncation limit
  - `settings.max_tokens` remains the optional stream-option cap where it is currently used
  - `session.conversation.max_tokens` remains the model-context budget used for compaction, overflow, and UI
  - Runtime code should read user settings from already-loaded typed state, not reload `tunacode.json`

## Deliverables

- Updated runtime wiring in:
  - `src/tunacode/core/agents/agent_components/agent_session_config.py`
  - `src/tunacode/core/agents/agent_components/agent_config.py`
  - `src/tunacode/core/compaction/controller.py`
  - `src/tunacode/tools/bash.py`
- Deleted files:
  - `src/tunacode/configuration/limits.py`
  - `src/tunacode/infrastructure/cache/caches/limits_settings.py`
- Updated tests covering the new ownership path
- Updated repo docs and generated tree references that currently name `limits.py`
- `AGENTS.md` date refresh because `src/` and docs will change

## Readiness

- Preconditions:
  - Parent research doc exists at `.artifacts/research/2026-04-11_15-47-09_limits-config-map.md`
  - Current git commit at planning time: `27f85393`
  - Current worktree status at planning time: untracked `.artifacts/research/2026-04-11_15-47-09_limits-config-map.md`
- Known implementation constraint:
  - `bash` is currently a singleton `AgentTool` in `src/tunacode/tools/bash.py:200`, while `_build_tools()` currently returns that singleton from `src/tunacode/core/agents/agent_components/agent_config.py:244`
- Known behavior invariants:
  - Agent stream-option `max_tokens` is currently sourced from `settings.max_tokens`
  - Compaction threshold `max_tokens` is currently sourced from `session.conversation.max_tokens`
  - Bash output truncation is currently sourced from `settings.max_command_output`

## Milestones

- M1: Move user-setting limits into typed runtime config objects
- M2: Rewire agent and compaction consumers away from `limits.py`
- M3: Rewire bash tool construction and delete obsolete modules
- M3.1: Audit, we should have LESS code then  before
- M4: Refresh tests, docs, and repo metadata

## Work Breakdown (Tasks)

### T001

- **Summary**: Extend the normalized runtime config so limit values live on typed session-derived settings instead of requiring `configuration.limits`
- **Owner**: JR developer
- **Estimate**: S
- **Dependencies**: None
- **Target milestone**: M1
- **Acceptance test**: `uv run pytest tests/unit/core/test_agent_session_config.py -q`
- **Files/modules touched**:
  - `src/tunacode/core/agents/agent_components/agent_session_config.py`
  - `tests/unit/core/test_agent_session_config.py` (new)

Implementation notes:
- Add typed fields for `max_command_output` and `max_tokens` to the normalized agent/session settings object.
- Populate those fields from `session.user_config["settings"]` inside `_normalize_session_config(...)`.
- Keep existing validation behavior for `request_delay`, `global_request_timeout`, `max_retries`, and `max_iterations`.

### T002

- **Summary**: Rewire agent construction to use normalized typed settings for stream-option `max_tokens` and agent-version hashing
- **Owner**: JR developer
- **Estimate**: M
- **Dependencies**: T001
- **Target milestone**: M2
- **Acceptance test**: `uv run pytest tests/unit/core/test_tinyagent_openrouter_model_config.py tests/unit/core/test_agent_init_debug.py tests/unit/core/test_agent_cache_abort.py -q`
- **Files/modules touched**:
  - `src/tunacode/core/agents/agent_components/agent_config.py`
  - `tests/unit/core/test_tinyagent_openrouter_model_config.py`
  - `tests/unit/core/test_agent_init_debug.py`
  - `tests/unit/core/test_agent_cache_abort.py`

Implementation notes:
- Remove the import of `get_max_tokens` from `src/tunacode/configuration/limits.py`.
- In `get_or_create_agent(...)`, derive the optional stream cap from the normalized session config returned by `_normalize_session_config(session)`.
- Preserve current behavior in `_build_stream_fn(...)`, `_merge_stream_options(...)`, and `_compute_agent_version(...)`; only change the source of the value.
- Replace tests that monkeypatch `agent_config.get_max_tokens` with setup that mutates the loaded session user config or normalized settings path.

### T003

- **Summary**: Rewire compaction summary generation to read the optional stream cap from session-backed typed settings instead of `configuration.limits`
- **Owner**: JR developer
- **Estimate**: S
- **Dependencies**: T001
- **Target milestone**: M2
- **Acceptance test**: `uv run pytest tests/unit/core/test_tinyagent_openrouter_model_config.py -q`
- **Files/modules touched**:
  - `src/tunacode/core/compaction/controller.py`
  - `tests/unit/core/test_tinyagent_openrouter_model_config.py`

Implementation notes:
- Remove the import of `get_max_tokens` from `src/tunacode/configuration/limits.py`.
- In `_generate_summary(...)`, read `self._state_manager.session.user_config["settings"]["max_tokens"]` directly or through a typed helper introduced in T001.
- Do not change threshold behavior in `should_compact(...)`, `check_and_compact(...)`, or `force_compact(...)`; those continue to use the `max_tokens` argument passed from `session.conversation.max_tokens`.
- Update the existing summary-generation test to assert against the session-backed setting path instead of a monkeypatched global helper.

### T004

- **Summary**: Convert bash tool construction from a singleton import to a runtime-configured tool instance that captures `max_command_output`
- **Owner**: JR developer
- **Estimate**: M
- **Dependencies**: T001
- **Target milestone**: M3
- **Acceptance test**: `uv run pytest tests/unit/tools/test_bash.py -q`
- **Files/modules touched**:
  - `src/tunacode/tools/bash.py`
  - `src/tunacode/core/agents/agent_components/agent_config.py`
  - `tests/unit/tools/test_bash.py` (new)

Implementation notes:
- Replace the module-level dependency on `get_command_limit()` with an explicit runtime value.
- Introduce a constructor/factory in `src/tunacode/tools/bash.py` that returns an `AgentTool` with an execute path capturing `max_command_output`.
- Update `_build_tools(...)` in `src/tunacode/core/agents/agent_components/agent_config.py` so it receives the typed settings object and passes `max_command_output` into the bash-tool factory.
- Preserve the public tool name, label, parameters, timeout validation, and truncation behavior; only change how the limit value is sourced.
- Add focused unit coverage for truncation using an injected `max_command_output` value.

### T005

- **Summary**: Delete the obsolete limits accessor module and its cache module, then remove tests that only existed to validate that duplicate load path
- **Owner**: JR developer
- **Estimate**: S
- **Dependencies**: T002, T003, T004
- **Target milestone**: M3
- **Acceptance test**: `rg -n "configuration\\.limits|limits_settings" src tests`
- **Files/modules touched**:
  - `src/tunacode/configuration/limits.py` (delete)
  - `src/tunacode/infrastructure/cache/caches/limits_settings.py` (delete)
  - `tests/unit/infrastructure/test_migrated_lru_cache_replacements.py`

Implementation notes:
- Remove the obsolete `from tunacode.configuration import limits` import and the `test_limits_settings_cache_clears_via_clear_all(...)` test.
- Leave unrelated cache tests intact.
- Ensure no remaining source or test import depends on the deleted modules.

### T006

- **Summary**: Update repo docs and metadata so they match the new ownership of command and token limits after `limits.py` is removed
- **Owner**: JR developer
- **Estimate**: S
- **Dependencies**: T005
- **Target milestone**: M4
- **Acceptance test**: `uv run python scripts/check_agents_freshness.py`
- **Files/modules touched**:
  - `docs/modules/configuration/configuration.md`
  - `docs/modules/tools/tools-system.md`
  - `docs/codebase-map/structure/tree-structure.txt`
  - `AGENTS.md`

Implementation notes:
- Replace references that currently say `limits.py` owns bash truncation or token limit accessors.
- Regenerate the structure-tree artifact after file deletion with `uv run python scripts/generate_structure_tree.py`.
- Update `AGENTS.md` `Last Updated` date because both `src/` and docs will change.

## Risks & Mitigations

- Risk: Bash tool factory changes could alter tool identity or concurrency wrapping behavior.
  - Mitigation: Keep the returned `AgentTool` metadata identical to the current singleton and continue routing it through `_apply_tool_concurrency_limit(...)`.

- Risk: The refactor could accidentally collapse two different token concepts into one.
  - Mitigation: Preserve current ownership boundaries explicitly:
    - `settings.max_tokens` for optional stream-option caps
    - `session.conversation.max_tokens` for context-window budgeting

- Risk: Tests currently monkeypatch deleted helpers.
  - Mitigation: Rewrite those tests to set session-backed typed config values directly.

- Risk: Documentation can become stale because multiple docs name `limits.py`.
  - Mitigation: Treat doc updates and `AGENTS.md` refresh as first-class deliverables in M4.

## Test Strategy

- Add one focused unit test for the new normalized settings fields.
- Add one focused unit test file for bash-tool truncation via injected runtime limit.
- Update existing unit tests that currently patch `get_max_tokens` to use session-backed config.
- Run targeted parity checks before broader gates:
  - `uv run pytest tests/unit/core/test_agent_session_config.py -q`
  - `uv run pytest tests/unit/tools/test_bash.py -q`
  - `uv run pytest tests/unit/core/test_tinyagent_openrouter_model_config.py tests/unit/core/test_agent_init_debug.py tests/unit/core/test_agent_cache_abort.py -q`
- After targeted tests pass, run the focused architectural/doc checks most relevant to the touched surface:
  - `uv run pytest tests/test_dependency_layers.py -v`
  - `uv run pytest tests/architecture/test_import_order.py`
  - `uv run python scripts/check_agents_freshness.py`

## References

- Research doc: `.artifacts/research/2026-04-11_15-47-09_limits-config-map.md`
- `src/tunacode/configuration/limits.py:18`
- `src/tunacode/core/agents/agent_components/agent_config.py:244`
- `src/tunacode/core/agents/agent_components/agent_config.py:540`
- `src/tunacode/core/compaction/controller.py:362`
- `src/tunacode/tools/bash.py:200`
- `src/tunacode/tools/bash.py:261`
- `src/tunacode/core/agents/agent_components/agent_session_config.py:13`
- `src/tunacode/core/session/state.py:94`
- `src/tunacode/core/session/state.py:99`
- `src/tunacode/ui/commands/model.py:114`
- `tests/unit/infrastructure/test_migrated_lru_cache_replacements.py:62`
- `tests/unit/core/test_tinyagent_openrouter_model_config.py:159`
- `tests/unit/core/test_tinyagent_openrouter_model_config.py:346`
- `docs/modules/configuration/configuration.md:35`
- `docs/modules/tools/tools-system.md:150`

## Final Gate

- **Output summary**: plan path, 4 milestones, 6 tasks ready
- **Next step**: proceed to execute-phase with `.artifacts/plan/2026-04-11_15-54-46_refactor-delete-limits-module.md`
