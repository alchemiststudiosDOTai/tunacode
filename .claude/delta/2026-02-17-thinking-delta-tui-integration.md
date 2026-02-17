---
title: Thinking delta TUI integration (core routing, panel wiring, commands, tests)
type: delta
link: thinking-delta-tui-integration
path: src/tunacode/core/agents/main.py
depth: 0
seams: [M]
ontological_relations:
  - affects: [[core]]
  - affects: [[ui]]
  - affects: [[commands]]
  - affects: [[tests]]
tags:
  - thinking
  - tinyagent
  - ui
  - streaming
  - tests
created_at: 2026-02-17T13:58:00-06:00
updated_at: 2026-02-17T13:58:00-06:00
uuid: 46cf76c2-8dad-4203-b27a-7d8f32de2a81
---

# Thinking delta TUI integration (core routing, panel wiring, commands, tests)

## Summary

Implemented end-to-end thinking stream integration for TunaCode TUI:

- Core now routes `thinking_delta` independently of `text_delta`
- UI now has a dedicated muted `#thinking-output` panel with throttled updates and bounded buffering
- `/thoughts` command toggles reasoning display on/off
- Final assistant response extraction now includes assistant `text` blocks only
- Added unit tests for core routing, thinking renderer behavior, and latest response extraction semantics

## Files changed

- `src/tunacode/core/agents/main.py`
- `src/tunacode/ui/renderers/thinking.py` (new)
- `src/tunacode/ui/styles/layout.tcss`
- `src/tunacode/ui/app.py`
- `src/tunacode/ui/commands/thoughts.py` (new)
- `src/tunacode/ui/commands/__init__.py`
- `tests/unit/core/test_thinking_stream_routing.py` (new)
- `tests/unit/ui/test_thinking_renderer.py` (new)
- `tests/unit/ui/test_app_latest_response_text.py` (new)

## Validation

- `uv run ruff check src/tunacode/core/agents/main.py src/tunacode/ui/app.py src/tunacode/ui/commands src/tunacode/ui/renderers/thinking.py` ✅
- `uv run pytest tests/unit/core/test_thinking_stream_routing.py tests/unit/ui/test_thinking_renderer.py tests/unit/ui/test_app_latest_response_text.py tests/unit/ui/test_command_contracts.py -q` ✅
- `uv run ruff check --fix .` ✅
- `uv run pytest` ⚠️ Fails in vendored `tinyAgent/tests/*` collection due import module resolution (`ModuleNotFoundError: No module named 'tests....'`)
