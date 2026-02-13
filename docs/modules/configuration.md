---
title: Configuration Layer
summary: User settings, model registry, path resolution, pricing tables, and feature flags.
read_when: Adding a new user-facing setting, supporting a new provider, or changing default behavior.
depends_on: [types, infrastructure]
feeds_into: [core, tools, ui]
---

# Configuration Layer

**Package:** `src/tunacode/configuration/`

## What

Everything that can be configured by the user or the project. This layer reads `tunacode.json`, resolves paths, loads the bundled model registry, and exposes typed accessors for limits, pricing, and feature flags.

## Key Files

| File | Purpose |
|------|---------|
| `defaults.py` | `DEFAULT_USER_CONFIG` dict -- the fallback for every setting. |
| `user_config.py` | `load_config()` reads `tunacode.json` from `~/.config/`. `load_config_with_defaults()` deep-merges user overrides onto defaults. |
| `settings.py` | `ApplicationSettings` dataclass -- app name, version, paths, internal tool list. `PathConfig` resolves `~/.config/tunacode.json`. |
| `models.py` | `load_models_registry()` parses `models_registry.json` (bundled). `parse_model_string()` splits `"provider:model_id"`. Accessors: `get_providers()`, `get_models_for_provider()`, `get_provider_env_var()`, `get_provider_base_url()`, `get_model_context_window()`, `validate_provider_api_key()`. |
| `paths.py` | Session storage directory, project ID derivation, home-dir resolution. |
| `limits.py` | `get_max_tokens()` -- resolves the effective max output tokens from user config. |
| `pricing.py` | Per-model pricing tables used to compute `CostBreakdown`. |
| `feature_flags.py` | Boolean feature toggles (e.g., experimental features). |
| `ignore_patterns.py` | Default file patterns excluded from grep/glob (`.git`, `node_modules`, etc.). |

## How

At startup, `StateManager.__init__()` calls `load_config_with_defaults()` to build the merged user config. This config dict is stored on `SessionState.user_config` and read by every other layer.

Model resolution flow:
1. `parse_model_string("openrouter:openai/gpt-4.1")` returns `("openrouter", "openai/gpt-4.1")`.
2. `get_provider_env_var("openrouter")` returns `"OPENROUTER_API_KEY"`.
3. `get_provider_base_url("openrouter")` returns the API endpoint from the bundled registry.
4. `get_model_context_window("openrouter:openai/gpt-4.1")` returns the token limit.

## Why

Centralizing configuration avoids scattered `os.getenv()` calls. The bundled `models_registry.json` means users never need to know provider URLs or env-var names -- just pick a provider and model from the registry.
