---
title: Shared theme variable contract for tunacode and nextstep palettes
type: delta
link: theme-variable-contract
path: src/tunacode/constants.py
depth: 0
seams: [A, S]
ontological_relations:
  - affects: [[ui]]
  - affects: [[theme-system]]
  - relates_to: [[nextstep-design-language]]
tags:
  - theme
  - textual
  - ui
  - nextstep
  - architecture
created_at: 2026-02-11T15:44:47-06:00
updated_at: 2026-02-11T15:44:47-06:00
uuid: d51a078b-a5cd-436e-a3dc-b3ee0f9ed197
---

# Shared theme variable contract for tunacode and nextstep palettes

## Summary

Established a single variable schema for both Textual themes so base TCSS can stay theme-agnostic and avoid missing-variable runtime paths.

## Changes

- Updated `src/tunacode/constants.py`:
  - Added `THEME_VARIABLE_CONTRACT` mapping variable names to palette keys.
  - Added `_build_theme_variables()` with fail-fast validation for missing palette keys.
  - Added missing shared palette keys to both `UI_COLORS` and `NEXTSTEP_COLORS`:
    - `bevel_light`
    - `bevel_dark`
    - `scrollbar_thumb`
    - `scrollbar_track`
  - Updated `build_tunacode_theme()` and `build_nextstep_theme()` to emit `variables` from the same contract.
  - Removed now-unused `NEXTSTEP_COLORS` entries (`window_content`, `title_bar`, `title_bar_text`).
- Added `tests/unit/ui/test_theme_variable_contract.py` to verify:
  - both palettes include all required keys,
  - both theme builders emit identical variable schemas,
  - variable values map correctly from each palette.

## Verification

- `uv run ruff check src/tunacode/constants.py tests/unit/ui/test_theme_variable_contract.py`
- `uv run pytest tests/unit/ui/test_theme_variable_contract.py -q`

Result: pass.
