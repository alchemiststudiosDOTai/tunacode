---
title: "limits config map research findings"
link: "limits-config-map-research"
type: research
ontological_relations:
  - relates_to: [[docs/modules/configuration/configuration.md]]
tags: [research, limits, configuration]
uuid: "C95E0715-8614-45F0-9EA0-039E255B0E48"
created_at: "2026-04-11T15:47:09-0500"
---

## Structure

- `src/tunacode/configuration/`
  - `limits.py` reads cached `UserSettings` values and exposes `get_command_limit()` and `get_max_tokens()`.
  - `defaults.py` defines default `settings.max_command_output` and `settings.max_tokens`.
  - `user_config.py` loads `tunacode.json`, deep-merges onto defaults, and validates `settings.max_command_output` and `settings.max_tokens`.
  - `models.py` defines `get_model_context_window()` for model registry context-window lookup.
- `src/tunacode/infrastructure/cache/caches/limits_settings.py`
  - Manual cache for the `settings` object used by `limits.py`.
- `src/tunacode/tools/bash.py`
  - Consumes `get_command_limit()` for bash output truncation.
- `src/tunacode/core/agents/agent_components/agent_config.py`
  - Consumes `get_max_tokens()` for agent stream options and agent-version hashing.
  - Uses `session.conversation.max_tokens` for context compaction thresholds.
- `src/tunacode/core/compaction/controller.py`
  - Accepts `max_tokens` as an argument for threshold checks.
  - Separately calls `get_max_tokens()` for compaction summary generation stream options.
- `src/tunacode/core/session/state.py`
  - Initializes and reloads `session.conversation.max_tokens` from `get_model_context_window()`.
- `src/tunacode/ui/commands/model.py`
  - Updates `session.conversation.max_tokens` when the current model changes.
- `src/tunacode/core/agents/main.py` and `src/tunacode/ui/app.py`
  - Read `session.conversation.max_tokens` for compaction retries and UI context gauges.

## Key Files

- `src/tunacode/configuration/limits.py:18` -> `_load_settings()` reads cached settings or loads `config["settings"]`.
- `src/tunacode/configuration/limits.py:35` -> `get_command_limit()` returns `_load_settings()["max_command_output"]`.
- `src/tunacode/configuration/limits.py:40` -> `get_max_tokens()` returns `_load_settings()["max_tokens"]`.
- `src/tunacode/configuration/defaults.py:31` -> default `settings.max_command_output` is `MAX_COMMAND_OUTPUT`.
- `src/tunacode/configuration/defaults.py:32` -> default `settings.max_tokens` is `None`.
- `src/tunacode/constants.py:29` -> `MAX_COMMAND_OUTPUT = 5000`.
- `src/tunacode/constants.py:30` -> `DEFAULT_CONTEXT_WINDOW = 200000`.
- `src/tunacode/configuration/user_config.py:52` -> `load_config()` opens the config file, merges onto defaults, and validates the merged config.
- `src/tunacode/configuration/user_config.py:187` -> `settings.max_command_output` is validated as `int`.
- `src/tunacode/configuration/user_config.py:191` -> `settings.max_tokens` is validated as `int | None`.
- `src/tunacode/infrastructure/cache/caches/limits_settings.py:15` -> `get_settings()` returns cached `UserSettings | None`.
- `src/tunacode/infrastructure/cache/caches/limits_settings.py:23` -> `set_settings()` stores cached `UserSettings`.
- `src/tunacode/tools/bash.py:261` -> bash output truncation reads `get_command_limit()`.
- `src/tunacode/core/agents/agent_components/agent_config.py:540` -> agent creation reads `get_max_tokens()`.
- `src/tunacode/core/agents/agent_components/agent_config.py:366` -> stream options are updated with `max_tokens` when non-`None`.
- `src/tunacode/core/agents/agent_components/agent_config.py:414` -> transform-context compaction uses `session.conversation.max_tokens`.
- `src/tunacode/core/compaction/controller.py:181` -> threshold check uses the passed `max_tokens` argument.
- `src/tunacode/core/compaction/controller.py:362` -> summary generation stream options use `get_max_tokens()`.
- `src/tunacode/core/session/state.py:99` -> new session sets `conversation.max_tokens = get_model_context_window(current_model)`.
- `src/tunacode/core/session/state.py:377` -> loaded session recomputes `max_tokens_value = get_model_context_window(current_model_value)`.
- `src/tunacode/ui/commands/model.py:114` -> model switch computes `new_max_tokens = get_model_context_window(full_model)`.
- `src/tunacode/ui/commands/model.py:120` -> model switch writes `session.conversation.max_tokens = new_max_tokens`.
- `src/tunacode/core/agents/main.py:177` -> request compaction uses `session.conversation.max_tokens`.
- `src/tunacode/core/agents/main.py:233` -> context overflow error reports `conversation.max_tokens or DEFAULT_CONTEXT_WINDOW`.
- `src/tunacode/ui/app.py:666` -> context panel uses `conversation.max_tokens or DEFAULT_CONTEXT_MAX_TOKENS`.
- `src/tunacode/ui/app.py:751` -> resource bar uses `conversation.max_tokens or DEFAULT_CONTEXT_MAX_TOKENS`.
- `src/tunacode/configuration/models.py:312` -> `get_model_context_window()` returns model registry `limit.context` or `DEFAULT_CONTEXT_WINDOW`.
- `src/tunacode/types/base.py:48` -> `UserSettings` includes `max_command_output`.
- `src/tunacode/types/base.py:49` -> `UserSettings` includes `max_tokens`.
- `src/tunacode/core/types/state_structures.py:45` -> `ConversationState.max_tokens` is a separate session field.
- `tests/unit/infrastructure/test_migrated_lru_cache_replacements.py:62` -> limits settings cache test covers `get_max_tokens()` caching across `clear_all()`.
- `tests/unit/core/test_session_state_model_registry_loading.py:20` -> state manager test asserts `session.conversation.max_tokens` is loaded from model registry context window.

## Patterns Found

- Cached settings reader
  - `src/tunacode/configuration/limits.py:21` reads from `limits_settings_cache.get_settings()`.
  - `src/tunacode/configuration/limits.py:31` stores the merged `settings` object in the cache.
  - `tests/unit/infrastructure/test_migrated_lru_cache_replacements.py:78` reads `111` from cached `get_max_tokens()`.
  - `tests/unit/infrastructure/test_migrated_lru_cache_replacements.py:85` still reads `111` after the file is rewritten.
  - `tests/unit/infrastructure/test_migrated_lru_cache_replacements.py:89` reads `222` after `clear_all()`.

- Command output limit path
  - `src/tunacode/configuration/defaults.py:31` sets default `max_command_output`.
  - `src/tunacode/configuration/user_config.py:187` validates `settings.max_command_output`.
  - `src/tunacode/configuration/limits.py:35` exposes `get_command_limit()`.
  - `src/tunacode/tools/bash.py:261` reads `get_command_limit()` immediately before truncating formatted bash output.
  - `rg -n "get_command_limit\\(" src tests docs` returned one source call site in `src/tunacode/tools/bash.py:261`.

- User-config token limit path
  - `src/tunacode/configuration/defaults.py:32` sets default `max_tokens` to `None`.
  - `src/tunacode/configuration/user_config.py:191` validates `settings.max_tokens`.
  - `src/tunacode/configuration/limits.py:40` exposes `get_max_tokens()`.
  - `src/tunacode/core/agents/agent_components/agent_config.py:540` reads `get_max_tokens()` during agent creation.
  - `src/tunacode/core/agents/agent_components/agent_config.py:543` includes that value in `_compute_agent_version(...)`.
  - `src/tunacode/core/agents/agent_components/agent_config.py:575` passes that value into `_build_agent_options(...)`.
  - `src/tunacode/core/agents/agent_components/agent_config.py:366` merges that value into `SimpleStreamOptions.max_tokens`.
  - `src/tunacode/core/compaction/controller.py:362` also passes `get_max_tokens()` into summary-generation stream options.
  - `rg -n "get_max_tokens\\(" src tests docs` returned two source call sites: `src/tunacode/core/agents/agent_components/agent_config.py:540` and `src/tunacode/core/compaction/controller.py:362`.

- Session context-window token path
  - `src/tunacode/configuration/models.py:333` reads the model registry `limit`.
  - `src/tunacode/configuration/models.py:337` reads `limit.context`.
  - `src/tunacode/configuration/models.py:341` returns that context value.
  - `src/tunacode/core/session/state.py:99` initializes `session.conversation.max_tokens` from `get_model_context_window(current_model)`.
  - `src/tunacode/core/session/state.py:377` recomputes `max_tokens_value` from `get_model_context_window(current_model_value)` while loading a saved session.
  - `src/tunacode/ui/commands/model.py:114` recomputes `new_max_tokens` on model change.
  - `src/tunacode/ui/commands/model.py:120` writes the session field.
  - `src/tunacode/core/agents/agent_components/agent_config.py:414` uses the session field for compaction transform context.
  - `src/tunacode/core/agents/main.py:177` and `src/tunacode/core/agents/main.py:187` use the session field for compaction flows.
  - `src/tunacode/ui/app.py:666` and `src/tunacode/ui/app.py:751` use the session field for UI context gauges.

- Compaction controller split
  - `src/tunacode/core/compaction/controller.py:136` defines `should_compact(..., max_tokens: int, ...)`.
  - `src/tunacode/core/compaction/controller.py:145` computes `threshold_tokens = max_tokens - reserve - self.keep_recent_tokens`.
  - `src/tunacode/core/compaction/controller.py:164` defines `check_and_compact(..., max_tokens: int, ...)`.
  - `src/tunacode/core/compaction/controller.py:181` calls `should_compact(messages, max_tokens=max_tokens)`.
  - `src/tunacode/core/compaction/controller.py:191` defines `force_compact(..., max_tokens: int, ...)`.
  - `src/tunacode/core/compaction/controller.py:362` uses `get_max_tokens()` only when building `SimpleStreamOptions` for summary generation.

## Dependencies

- `src/tunacode/configuration/defaults.py:23` `settings` block -> `src/tunacode/configuration/user_config.py:63` merged config -> `src/tunacode/configuration/user_config.py:164` validated `UserSettings` -> `src/tunacode/configuration/limits.py:28` loaded `config["settings"]`.
- `src/tunacode/configuration/limits.py:21` -> `src/tunacode/infrastructure/cache/caches/limits_settings.py:15`.
- `src/tunacode/configuration/limits.py:31` -> `src/tunacode/infrastructure/cache/caches/limits_settings.py:23`.
- `src/tunacode/configuration/limits.py:35` -> `src/tunacode/tools/bash.py:261`.
- `src/tunacode/configuration/limits.py:40` -> `src/tunacode/core/agents/agent_components/agent_config.py:540`.
- `src/tunacode/configuration/limits.py:40` -> `src/tunacode/core/compaction/controller.py:362`.
- `src/tunacode/configuration/models.py:312` -> `src/tunacode/core/session/state.py:99`.
- `src/tunacode/configuration/models.py:312` -> `src/tunacode/core/session/state.py:377`.
- `src/tunacode/configuration/models.py:312` -> `src/tunacode/ui/commands/model.py:114`.
- `src/tunacode/core/session/state.py:99` / `src/tunacode/ui/commands/model.py:120` -> `src/tunacode/core/agents/agent_components/agent_config.py:414`.
- `src/tunacode/core/session/state.py:99` / `src/tunacode/ui/commands/model.py:120` -> `src/tunacode/core/agents/main.py:177`.
- `src/tunacode/core/session/state.py:99` / `src/tunacode/ui/commands/model.py:120` -> `src/tunacode/ui/app.py:666`.

## Symbol Index

- `src/tunacode/configuration/limits.py:18` -> `_load_settings() -> UserSettings`
- `src/tunacode/configuration/limits.py:35` -> `get_command_limit() -> int`
- `src/tunacode/configuration/limits.py:40` -> `get_max_tokens() -> int | None`
- `src/tunacode/infrastructure/cache/caches/limits_settings.py:15` -> `get_settings() -> UserSettings | None`
- `src/tunacode/infrastructure/cache/caches/limits_settings.py:23` -> `set_settings(settings: UserSettings) -> None`
- `src/tunacode/infrastructure/cache/caches/limits_settings.py:27` -> `clear_settings_cache() -> None`
- `src/tunacode/configuration/models.py:312` -> `get_model_context_window(model_string: str) -> int`
- `src/tunacode/types/base.py:40` -> `class UserSettings(TypedDict)`
- `src/tunacode/core/types/state_structures.py:39` -> `class ConversationState`
