---
title: Disable live agent text streaming by default and enable thoughts panel by default
type: delta
link: disable-agent-text-streaming-default
path: src/tunacode/ui/app.py
depth: 0
seams: [M]
ontological_relations:
  - affects: [[ui]]
  - affects: [[core]]
  - affects: [[configuration]]
  - affects: [[tests]]
tags:
  - streaming
  - ui
  - tinyagent
  - abort-handling
  - config
created_at: 2026-02-20T16:05:28-06:00
updated_at: 2026-02-20T16:07:42-06:00
uuid: d9b8ee5e-078c-48b9-9a64-b09cd566ed29
---

# Disable live agent text streaming by default and enable thoughts panel by default

## Summary

Turned off live text streaming rendering in the TUI by default to reduce visual jitter.

Added `settings.stream_agent_text` (default `false`) and wired request creation to pass the streaming callback only when that setting is enabled.

Changed session defaults so the thoughts panel starts enabled (`SessionState.show_thoughts = True`) to keep reasoning visible even with text streaming disabled.

Kept tinyagent event streaming in place for tool lifecycle handling and final message assembly.

## Key behavioral detail

`RequestOrchestrator._handle_message_update()` now appends `text_delta` content to `_debug_raw_stream_accum` even when no streaming callback is attached. This preserves interrupted-response recovery behavior when live streaming output is disabled.

## Files changed

- `src/tunacode/ui/app.py`
- `src/tunacode/configuration/defaults.py`
- `src/tunacode/core/agents/main.py`
- `src/tunacode/core/session/state.py`
- `tests/unit/core/test_thinking_stream_routing.py`
- `tests/unit/core/test_session_state_defaults.py` (new)
- `tests/unit/configuration/test_default_config_stream_agent_text.py` (new)
- `tests/unit/ui/test_stream_agent_text_setting.py` (new)

## Validation

- `uv run ruff check --fix src/tunacode/ui/app.py src/tunacode/core/agents/main.py src/tunacode/core/session/state.py src/tunacode/configuration/defaults.py tests/unit/core/test_thinking_stream_routing.py tests/unit/core/test_session_state_defaults.py tests/unit/configuration/test_default_config_stream_agent_text.py tests/unit/ui/test_stream_agent_text_setting.py` ✅
- `uv run pytest tests/unit/core/test_thinking_stream_routing.py tests/unit/core/test_session_state_defaults.py tests/unit/configuration/test_default_config_stream_agent_text.py tests/unit/ui/test_stream_agent_text_setting.py -q` ✅
- `uv run ruff check .` ✅
