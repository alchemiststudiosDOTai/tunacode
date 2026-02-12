---
title: Missing t/s after Rust provider swap due to usage shape mismatch
link: rust-usage-shape-throughput-missing
type: debug
created_at: 2026-02-11T22:56:00-06:00
updated_at: 2026-02-11T22:56:00-06:00
tags:
  - tinyagent
  - alchemy
  - usage
  - throughput
  - ui
  - metrics
---

# Missing t/s after Rust provider swap due to usage shape mismatch

## Symptom

The agent response footer stopped showing throughput (`t/s`) after switching from Python OpenRouter streaming to the Rust alchemy provider.

## Root Cause

`_handle_stream_message_end()` stores usage only when `_parse_openrouter_usage(msg["usage"])` returns non-`None`.

The parser previously expected OpenRouter-style keys (`prompt_tokens`, `completion_tokens`, `cacheRead`).

Rust alchemy (`alchemy-llm`) emits usage with a different shape (`input`, `output`, `cache_read`, nested `cost.total`), so parsing returned `None`, leaving `last_call_usage.completion_tokens == 0`.

## Evidence

- TunaCode usage parse path: `src/tunacode/core/agents/main.py`
- Rust usage struct shape confirmed in:
  - `/Users/tuna/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/alchemy-llm-0.1.1/src/types/usage.rs`
  - `/Users/tuna/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/alchemy-llm-0.1.1/src/providers/openai_completions.rs`

## Fix

Expanded `_parse_openrouter_usage()` to support all known shapes:

- OpenRouter raw SSE keys
- tinyagent normalized OpenRouter keys
- Rust alchemy keys (`input`, `output`, `cache_read`, `cost.total`)

Also added key-resolution helpers to avoid falsey `or` behavior masking valid zero values.

Added fail-loud usage recording in stream handlers:

- Parse usage at both `message_end` and `turn_end` events.
- Warn when `usage` is missing or does not match known schema.
- Log usage keys/payload for rapid provider contract debugging.

## Tests Added

`tests/unit/core/test_openrouter_usage_metrics.py`

- `test_parse_openrouter_usage_supports_alchemy_usage_shape`
- `test_parse_openrouter_usage_supports_openrouter_cache_read_input_tokens`

## Verification

- `uv run pytest tests/unit/core/test_openrouter_usage_metrics.py -q`
- `uv run ruff check .`
