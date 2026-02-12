---
title: TinyAgent provider guard removal + OpenAI-compatible base_url path
type: delta
link: tinyagent-base-url-provider-flex
path: src/tunacode/core
depth: 0
seams: [A, M, S]
ontological_relations:
  - relates_to: [[tinyagent-migration]]
  - affects: [[agents]]
  - affects: [[compaction]]
  - affects: [[tests]]
tags:
  - tinyagent
  - openroutermodel
  - base-url
  - api-key-resolution
  - compaction
created_at: 2026-02-11T17:35:35-06:00
updated_at: 2026-02-11T17:35:35-06:00
uuid: b012f14b-6291-42c0-9601-10b5668dcba4
---

# TinyAgent provider guard removal + OpenAI-compatible base_url path

## Summary

Unblocked non-`openrouter:` models when using `OpenRouterModel(base_url=...)`.

- Removed hard provider guard from agent model construction.
- Removed hard provider guard from compaction model construction.
- Added API key fallback behavior for non-openrouter providers:
  - use provider-specific env key first
  - fallback to `OPENAI_API_KEY`
- Added tests for base URL propagation, non-openrouter provider support, and normalized usage payload parsing (`cacheRead`).
- Removed dead shim module `src/tunacode/core/tinyagent/openrouter_usage.py`.

## Key changes

- `src/tunacode/core/agents/agent_components/agent_config.py`
  - `_build_tinyagent_model()` now accepts any provider id parsed from `provider:model`.
  - `_build_api_key_resolver()` validates env mapping type and adds `OPENAI_API_KEY` fallback.
- `src/tunacode/core/compaction/controller.py`
  - `_build_model()` no longer blocks non-openrouter providers.
  - `_resolve_api_key()` now mirrors provider-first then `OPENAI_API_KEY` fallback.
- `tests/unit/core/test_tinyagent_openrouter_model_config.py` (new)
  - Base URL propagation test.
  - Non-openrouter provider with base URL test.
  - API key fallback tests for agent and compaction paths.
- `tests/unit/core/test_openrouter_usage_metrics.py`
  - Added normalized usage coverage for top-level `cacheRead` key.
- `tests/unit/core/test_compaction_controller_outcomes.py`
  - Updated capability test to expect missing provider API key behavior for non-openrouter provider.

## Verification

- `uv run ruff check . --fix`
- `uv run ruff check .`
- `uv run pytest tests/unit/core/test_tinyagent_openrouter_model_config.py tests/unit/core/test_openrouter_usage_metrics.py tests/unit/core/test_compaction_controller_outcomes.py tests/test_compaction.py`
