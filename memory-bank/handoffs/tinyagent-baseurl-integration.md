# Handoff: TinyAgent base_url Integration

**Date:** 2026-02-11
**Status:** TinyAgent updated, PyPI release pending

## What Changed

TinyAgent added native `base_url` support for OpenAI-compatible endpoints:
- Python provider: `stream_openrouter` now accepts `base_url` parameter
- Rust binding provider: `stream_alchemy_openrouter` / `stream_alchemy_openai_completions`
- New `OpenRouterModel` class for configuration

## Files to Modify in TunaCode

### 1. `/root/tunacode/src/tunacode/core/tinyagent/openrouter_usage.py`
**Current:** Custom HTTP wrapper that hardcodes `OPENROUTER_API_URL`
**Action:** Replace with TinyAgent's native `stream_openrouter` using `OpenRouterModel`

### 2. `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py`
**Current:** `_build_tinyagent_model()` only allows `openrouter:` provider prefix
**Lines 243-262:** Hardcoded check rejects other providers
**Action:**
- Remove the `if provider_id != "openrouter":` check
- Support arbitrary provider:model format
- Pass `base_url` from config to TinyAgent

### 3. `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py`
**Current:** `_build_stream_fn()` wraps custom `stream_openrouter_with_usage`
**Action:** Replace with TinyAgent's native streaming (once usage data confirmed)

## Configuration Flow

User sets base URL via:
- `--baseurl` CLI flag → stored in `OPENAI_BASE_URL` env var
- User config: `user_config.env.OPENAI_BASE_URL`

This needs to be passed through to TinyAgent's `OpenRouterModel(base_url=...)`

## Testing Notes

TinyAgent team confirmed working with:
- OpenRouter default endpoint
- Chutes endpoint: `https://llm.chutes.ai/v1/chat/completions`
- Model: `Qwen/Qwen3-32B`

## Migration Path

1. Update TinyAgent dependency when PyPI releases
2. Replace custom wrapper with native TinyAgent streaming
3. Update model validation to allow arbitrary providers
4. Thread `base_url` from config through to TinyAgent
5. Remove `openrouter_usage.py` if native usage data works

## Local TinyAgent Location

`/root/tinyAgent/` - already has latest changes pulled (commit `2e1fcdb`)

## Docs Reference

TinyAgent docs:
- `docs/api/openai-compatible-endpoints.md`
- `docs/api/providers.md`
