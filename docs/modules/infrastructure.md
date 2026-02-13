---
title: Infrastructure Layer
summary: Thread-safe caching infrastructure with pluggable invalidation strategies and named cache instances.
read_when: Adding a new cached resource, debugging stale cache state, or changing invalidation behavior.
depends_on: [types]
feeds_into: [configuration, core, tools]
---

# Infrastructure Layer

**Package:** `src/tunacode/infrastructure/`

## What

Generic caching infrastructure. Provides a global `CacheManager` singleton, a `Cache` class with per-key metadata, and pluggable `CacheStrategy` objects that decide when entries are stale.

Concrete cache instances (agents, models registry, context, limits/settings) are pre-registered in sub-modules.

## Key Files

| File | Purpose |
|------|---------|
| `cache/manager.py` | `CacheManager` singleton and `Cache` class. Thread-safe via `threading.RLock`. |
| `cache/strategies.py` | `CacheStrategy` protocol and built-in strategies (e.g., TTL, version-based). |
| `cache/metadata.py` | Metadata types attached to cache entries (version stamps, timestamps). |
| `cache/caches/__init__.py` | Package that imports and exposes all named cache modules. |
| `cache/caches/agents.py` | `get_agent()` / `set_agent()` / `invalidate_agent()` -- caches tinyagent `Agent` instances keyed by model name. |
| `cache/caches/models_registry.py` | `get_registry()` / `set_registry()` -- caches the parsed `models_registry.json`. |
| `cache/caches/tunacode_context.py` | `get_context()` -- caches the guide file (`AGENTS.md`) content. Uses file-stat-based staleness. |
| `cache/caches/limits_settings.py` | Caches resolved limit/setting values to avoid re-parsing user config on every call. |
| `file_filter.py` | Shared file-filtering logic used by tools and UI. |

## How

1. At import time, each `cache/caches/*.py` module registers a named cache with the global `CacheManager`.
2. Callers use the typed accessor functions (`get_agent()`, `set_agent()`) -- they never interact with `CacheManager` directly.
3. `CacheStrategy.is_valid()` is called on every `get()`. If it returns `False`, the entry is evicted transparently.
4. `CacheManager.clear_all()` wipes every registered cache -- used in tests for deterministic cleanup.

## Why

Agent creation is expensive (model resolution, tool schema generation, system prompt loading). Caching avoids reconstructing agents on every user message. The strategy abstraction lets different caches use different staleness rules (file-stat for guide files, version-hash for agents, TTL for settings).
