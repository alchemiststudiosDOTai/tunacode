---
title: Refactor UI lifecycle functions into AppLifecycle with persistent ownership
type: delta
link: app-lifecycle-class-refactor
path: src/tunacode/ui/lifecycle.py
depth: 0
seams: [M]
ontological_relations:
  - affects: [[ui]]
  - affects: [[lifecycle]]
  - affects: [[state-management]]
tags:
  - ui
  - lifecycle
  - refactor
  - setup-flow
created_at: 2026-02-20T16:25:25-06:00
updated_at: 2026-02-20T16:25:25-06:00
uuid: 18a250e5-28d9-4b2a-be2f-ed3a667378fd
---

# Refactor UI lifecycle functions into AppLifecycle with persistent ownership

## Summary

Replaced free lifecycle functions with an `AppLifecycle` class in `src/tunacode/ui/lifecycle.py`.

Updated `TextualReplApp` to persist a single lifecycle instance (`self._lifecycle`) and reuse that instance across `on_mount` and `on_unmount`.

This removes function-level indirection and makes REPL startup idempotent through `_repl_started` inside lifecycle state.

## Files changed

- `src/tunacode/ui/PLAN.md`
- `src/tunacode/ui/lifecycle.py`
- `src/tunacode/ui/app.py`

## Behavior notes

- Theme and session metadata initialization stay in mount flow.
- Setup dismissal still proceeds into REPL startup.
- Slopgotchi timer ownership remains on `TextualReplApp._slopgotchi_timer`, with lifecycle start/stop helpers managing it.
- `on_unmount` now fails loudly if lifecycle was never initialized.

## Validation

- `uv run ruff check src/tunacode/ui/app.py src/tunacode/ui/lifecycle.py` ✅
- `uv run pytest tests/unit/ui/test_supported_themes.py -q` ✅
- `uv run ruff check .` ✅
