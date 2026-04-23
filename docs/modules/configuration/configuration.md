---
title: Configuration Layer
summary: User settings, model registry, path resolution, pricing tables, and ignore patterns.
read_when: Adding a new user-facing setting, supporting a new provider, or changing default behavior.
depends_on: [types, infrastructure]
feeds_into: [core, tools, ui]
when_to_read:
  - Adding a new user-facing setting
  - Supporting a new provider
  - Changing default behavior
last_updated: "2026-04-04"
---

# Configuration Layer

**Package:** `src/tunacode/configuration/`

## What

Everything that can be configured by the user or the project. This layer reads `tunacode.json`, resolves paths, loads the bundled model registry, and exposes typed accessors for limits, pricing, and ignore patterns.

Registry-backed metadata reads are lazy on a cold cache. Call sites that need provider env vars, provider base URLs, context windows, or pricing can read through the configuration accessors without preloading `models_registry.json` first.

User config is now a validated typed schema rather than an ad hoc nested dict. Partial config files are deep-merged onto `DEFAULT_USER_CONFIG`, then validated into `UserConfig` / `UserSettings` before the rest of the app reads from them.

## Key Files

| File | Purpose |
|------|---------|
| `defaults.py` | `DEFAULT_USER_CONFIG: UserConfig` -- the full typed fallback for every persisted setting, including nested `ripgrep` settings. |
| `user_config.py` | `load_config()` reads `tunacode.json`, deep-merges overrides onto defaults, validates the merged result, and raises `ConfigurationError` for malformed JSON, invalid schema values, or write/read failures. `load_config_with_defaults()` returns a validated full config even when no file exists. |
| `settings.py` | `ApplicationSettings` dataclass -- app name, version, paths, internal tool list. `PathConfig` resolves `~/.config/tunacode.json`. |
| `models.py` | `load_models_registry()` parses `models_registry.json` (bundled) and populates the manual models-registry cache. `parse_model_string()` splits `"provider:model_id"`. Read helpers back lazy accessors such as `get_provider_env_var()`, `get_provider_base_url()`, `get_provider_alchemy_api()`, and `get_model_context_window()`. |
| `paths.py` | Session storage directory, project ID derivation, home-dir resolution. |
| `limits.py` | `get_max_tokens()` -- resolves the effective max output tokens from typed user settings. |
| `pricing.py` | Registry-backed pricing lookup and cost formatting/calculation helpers. `get_model_pricing()` now reads through the same lazy registry path as the metadata accessors. |
| `ignore_patterns.py` | Built-in ignore defaults plus shared helpers for loading `.gitignore` rules, tolerating unreadable ignore files by falling back to defaults, and compiling reusable `pathspec` matchers. |

## Related Docs

- [`models-registry.md`](models-registry.md) -- contributor workflow for refreshing `models_registry.json` from models.dev and applying TunaCode-specific normalization rules.

## How

At startup, `StateManager.__init__()` calls `load_config_with_defaults()` to build the merged user config. The result is stored on `SessionState.user_config` as a validated `UserConfig`, and downstream code reads from that schema with direct indexed access instead of repetitive `.get()` fallback chains.

Config load flow:

1. `DEFAULT_USER_CONFIG` provides the complete expected schema.
2. `load_config()` reads `~/.config/tunacode.json` when present.
3. `_merge_config_value()` recursively overlays persisted values onto defaults, so partial nested config is allowed.
4. `validate_user_config()` converts the merged object into typed `UserConfig` / `UserSettings` / nested settings structures.
5. Invalid JSON, missing required keys, wrong types, and write/read failures are surfaced as `ConfigurationError`.

Model resolution flow:
1. `parse_model_string("openrouter:openai/gpt-4.1")` returns `("openrouter", "openai/gpt-4.1")`.
2. `get_provider_env_var("openrouter")` lazy-loads the registry on first access and returns `"OPENROUTER_API_KEY"`.
3. `get_provider_base_url("openrouter")` returns the API endpoint from the bundled registry without requiring a manual preload.
4. `get_model_context_window("openrouter:openai/gpt-4.1")` resolves the token limit through the same lazy read path.
5. `get_model_pricing("openrouter:openai/gpt-4.1")` resolves the pricing record from the same cached registry document.

## Why

Centralizing configuration avoids scattered `os.getenv()` calls and defensive shape checks at every call site. The bundled `models_registry.json` means users never need to know provider URLs or env-var names -- just pick a provider and model from the registry. The validated config schema also makes startup failures explicit instead of silently tolerating malformed settings.
