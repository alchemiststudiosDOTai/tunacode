---
title: Slopgotchi pet widget added to context inspector
type: delta
link: slopgotchi-pet-widget
path: src/tunacode/ui/slopgotchi/
depth: 0
seams: [A, M]
ontological_relations:
  - affects: [[ui]]
  - affects: [[context-panel]]
tags:
  - ui
  - slopgotchi
  - context-panel
created_at: 2026-02-16T16:12:22-06:00
updated_at: 2026-02-16T16:12:22-06:00
uuid: a7c3e810-4f1a-4b9e-9d3f-7e8b2a6c1d04
---

# Slopgotchi pet widget added to context inspector

## Summary

Added a decorative ASCII pet widget to the context inspector panel. Clicking the pet shows a red heart and cycles through ASCII art frames with a bounce animation.

## Changes

- `src/tunacode/ui/slopgotchi/` — New module (renamed from `tamagochi/`)
  - `__init__.py` — Exports `SlopgotchiHandler`, `SlopgotchiPanelState`
  - `panel.py` — Click handler, ASCII frame cycling, heart animation, margin bounce
- `src/tunacode/ui/app.py` — Compose includes `#field-pet`, `on_click` walks parent tree to detect pet clicks, `_touch_slopgotchi` and `_refresh_slopgotchi` methods
- `src/tunacode/ui/context_panel.py` — Updated imports from slopgotchi module
- `src/tunacode/ui/styles/layout.tcss` — `#field-pet` styling
- `tests/unit/ui/test_context_panel_summary.py` — Pet widget assertions

## Key Lessons

- **Textual click detection:** Do NOT use `on_mouse_down` with `event.control is widget` for Static widgets. Use `on_click` and walk `event.widget.parent` tree checking IDs.
- **Rich Text in Static:** Never apply a single style to entire `Text(art, style=...)` — it colors whitespace too. Build with `.append()` per segment instead.
