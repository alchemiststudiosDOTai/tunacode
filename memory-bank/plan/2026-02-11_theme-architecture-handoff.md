# Theme Architecture Handoff

## Status: COMPLETED (2026-02-11)

All steps executed. The unified CSS variable contract is live. `theme-nextstep.tcss` deleted. Both palettes emit the same variable set. 14 themes supported.

---

## Problem (historical)

A previous agent treated NeXTSTEP as one optional theme among many and created divergent variable sets between the tunacode and nextstep palettes. This led to:

1. `UI_COLORS` and `NEXTSTEP_COLORS` defining different variable keys
2. Hardcoded hex in TCSS files
3. 352 lines of per-theme CSS overrides in `theme-nextstep.tcss`
4. Any CSS referencing `$bevel-light` broke in dark theme; `$scrollbar-color` broke in light theme

## Resolution

NeXTSTEP is not a theme -- it is the structural design language. Every theme (dark, light, catppuccin, dracula, etc.) follows the same NeXTSTEP structural design: beveled borders, zone-based layout, 3D affordances, inset input fields, raised panels. A "theme" is only a color palette swap.

### What was done

1. Defined `THEME_VARIABLE_CONTRACT` -- a single tuple of `(css_variable, palette_key)` pairs that every theme must satisfy
2. Added `_build_theme_variables()` with fail-fast validation for missing palette keys
3. Both `UI_COLORS` and `NEXTSTEP_COLORS` now include all 6 shared keys: `bevel_light`, `bevel_dark`, `border`, `muted`, `scrollbar_thumb`, `scrollbar_track`
4. Both `build_tunacode_theme()` and `build_nextstep_theme()` emit identical variable schemas via the contract
5. Added `BUILTIN_THEME_PALETTES` with 12 additional palettes (catppuccin-latte, catppuccin-mocha, dracula, flexoki, gruvbox, monokai, nord, solarized-light, textual-ansi, textual-dark, textual-light, tokyo-night)
6. `wrap_builtin_themes()` injects contract variables into Textual built-in themes
7. All TCSS files rewritten to use only `$variables` -- zero hardcoded hex
8. Deleted `theme-nextstep.tcss` and removed it from `CSS_PATH` in `app.py`
9. Tests added: `tests/unit/ui/test_theme_variable_contract.py`, `tests/unit/ui/test_status_bar_layout.py`

### Verification

- `uv run pytest tests/unit/ui/ -q` -- pass
- `uv run ruff check .` -- pass
- Visual verification screenshots in `memory-bank/plan/assets/verification/`

## Current Architecture

See `.claude/patterns/unified-css-theme-architecture.md` for the canonical reference.

## Reference

- CSS files: `src/tunacode/ui/styles/` (4 files: layout, panels, widgets, modals)
- Theme builders: `src/tunacode/constants.py`
- CSS loading: `src/tunacode/ui/app.py` `CSS_PATH`
- NeXTSTEP UI skill: `.claude/skills/neXTSTEP-ui/SKILL.md`
