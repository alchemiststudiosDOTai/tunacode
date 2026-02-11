---
title: StatusBar content-row regression fix (top bevel + visible text)
type: delta
link: statusbar-content-row-regression-fix
path: src/tunacode/ui/styles/widgets.tcss
depth: 0
seams: [S]
ontological_relations:
  - affects: [[ui]]
  - affects: [[tests]]
  - relates_to: [[theme-revamp]]
tags:
  - ui
  - statusbar
  - textual
  - regression
  - css
created_at: 2026-02-11T16:18:02-06:00
updated_at: 2026-02-11T16:18:02-06:00
uuid: 8c4190e8-52f4-4025-adc1-88c2a5d4b96f
---

# StatusBar content-row regression fix

## Summary

The status bar gained a top bevel border during the UI revamp, but its height remained `1`. In Textual, border rows consume layout space, so a one-row widget with a top border leaves zero content rows. This caused bottom-bar information text to render incorrectly / disappear.

## Changes

- Updated `src/tunacode/ui/styles/widgets.tcss`:
  - `StatusBar` height changed from `1` to `2`.
  - Keeps the top bevel border while restoring one visible content row.
- Added regression test `tests/unit/ui/test_status_bar_layout.py`:
  - Asserts `status_bar.content_region.height >= 1` when app CSS is loaded.

## Verification

- `uv run pytest tests/unit/ui/test_status_bar_layout.py tests/unit/ui/test_supported_themes.py -q`
- `uv run pytest tests/unit/ui -q`
- `uv run ruff check .`
