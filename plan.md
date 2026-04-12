---
title: Refactor Plan - Centralize Theme Field Extraction
summary: Plan to centralize theme field extraction with defensive getattr calls in constants.py.
when_to_read:
  - Before starting the theme field extraction refactor
last_updated: "2026-04-12"
---

# Refactor Plan: Centralize Theme Field Extraction

## Problem

The codebase uses defensive `getattr()` calls extensively when working with Textual's `Theme` objects. Textual 4.0.0 leaves some built-in themes with unresolved fields at runtime, even though the static types suggest these fields should exist.

Current pattern (scattered in `constants.py`):
```python
secondary=getattr(theme, "secondary", None),
warning=getattr(theme, "warning", None),
error=getattr(theme, "error", None),
success=getattr(theme, "success", None),
accent=getattr(theme, "accent", None),
luminosity_spread=getattr(theme, "luminosity_spread", 0.15),
text_alpha=getattr(theme, "text_alpha", 0.95),
```

This is code smell: typed codebase using runtime defensive programming to mask external library inconsistencies.

## Solution

Centralize the workaround only if doing so makes `constants.py` shorter or at least clearly easier to read. The goal is to reduce the smell, not to add ceremony.

If a `_ThemeFields` + helper approach ends up making this small file more verbose or less idiomatic, prefer the simpler implementation and keep the workaround local.

### Implementation

1. **Prefer the smallest readable refactor**
   - Only extract logic that is truly repeated or meaningfully clarifies intent
   - Keep the resulting code idiomatic Python, not over-abstracted
   - Avoid introducing helper structures if they add more noise than they remove

2. **If using `_extract_theme_fields()`**
   - Keep it small and explicit
   - Use a private typed structure rather than `Any`
   - Centralize only the Textual-runtime-inconsistency workaround

3. **Update `_wrap_builtin_theme()`**
   - Keep fallback logic for color resolution
   - Prefer whichever version is easier to scan in-place: direct attributes with a tiny helper, or one extracted fields object

4. **Result**
   - Reduce the smell without making the code longer or harder to follow
   - Keep the implementation maintainable and type-friendly

## Files Modified

- `src/tunacode/constants.py`

## Code Changes

### Add `_ThemeFields` and `_extract_theme_fields()`

```python
from typing import TypedDict


class _ThemeFields(TypedDict):
    primary: str
    secondary: str | None
    warning: str | None
    error: str | None
    success: str | None
    accent: str | None
    foreground: str | None
    background: str | None
    surface: str | None
    panel: str | None
    boost: str | None
    dark: bool
    luminosity_spread: float
    text_alpha: float
    variables: dict[str, str]


def _extract_theme_fields(theme: Theme) -> _ThemeFields:
    """Extract all theme fields with safe defaults.

    Centralizes the 'Textual themes may be incomplete' problem to one location.
    Textual 4.0.0 leaves some built-ins with unresolved fields at runtime.
    """
    return {
        "primary": theme.primary,
        "secondary": getattr(theme, "secondary", None),
        "warning": getattr(theme, "warning", None),
        "error": getattr(theme, "error", None),
        "success": getattr(theme, "success", None),
        "accent": getattr(theme, "accent", None),
        "foreground": getattr(theme, "foreground", None),
        "background": getattr(theme, "background", None),
        "surface": getattr(theme, "surface", None),
        "panel": getattr(theme, "panel", None),
        "boost": getattr(theme, "boost", None),
        "dark": theme.dark,
        "luminosity_spread": getattr(theme, "luminosity_spread", 0.15),
        "text_alpha": getattr(theme, "text_alpha", 0.95),
        "variables": theme.variables,
    }
```

### Update `_wrap_builtin_theme()`

```python
def _wrap_builtin_theme(theme: Theme, palette: Mapping[str, str]) -> Theme:
    """Re-register a Textual built-in theme with contract variables injected."""
    from textual.theme import Theme as ThemeCls

    fields = _extract_theme_fields(theme)
    merged_vars = {**fields["variables"], **_build_theme_variables(palette)}
    fallback_colors = BUILTIN_THEME_COLOR_FALLBACKS.get(theme.name, {})

    def resolve_color(field: str) -> str | None:
        value = fields[field]
        if value in (None, "ansi_default"):
            return fallback_colors.get(field, value)
        return value

    return ThemeCls(
        name=theme.name,
        primary=fields["primary"],
        secondary=fields["secondary"],
        warning=fields["warning"],
        error=fields["error"],
        success=fields["success"],
        accent=fields["accent"],
        foreground=resolve_color("foreground"),
        background=resolve_color("background"),
        surface=resolve_color("surface"),
        panel=resolve_color("panel"),
        boost=fields["boost"],
        dark=fields["dark"],
        luminosity_spread=fields["luminosity_spread"],
        text_alpha=fields["text_alpha"],
        variables=merged_vars,
    )
```

## Benefits

1. **Reduced smell**: The Textual inconsistency workaround is easier to spot and reason about
2. **Readable code**: The file should stay compact and easy to scan
3. **Maintainable**: Defaults and fallbacks remain easy to adjust
4. **Type-friendly**: Uses explicit types if extraction is introduced, and avoids `Any`
5. **Idiomatic**: Keeps the solution Pythonic instead of adding unnecessary abstraction

## Testing

- Run `make test` to ensure theme wrapping still works
- Verify all built-in themes (catppuccin, dracula, gruvbox, etc.) load correctly
- Check that custom themes (tunacode, nextstep) are unaffected

## Notes

- This is a pure refactor, no behavioral changes
- Do not treat helper extraction as mandatory if it makes the code more verbose than the original
- Do not use `Any` in the helper return type; keep the extracted structure explicit if a helper is introduced
- Prefer the most readable and idiomatic Python solution, even if that means a smaller-scope cleanup than the original draft
- The workaround comment about Textual 4.0.0 should live next to whichever code path actually carries the workaround
