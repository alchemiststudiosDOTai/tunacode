# Theme Architecture Handoff

## Status: BLOCKED -- needs proper architecture before any more CSS work

## What Happened

A previous agent (me) was asked to improve the CSS to match the dream UI mockups in `docs/images/dream-ui/`. Instead of thinking about the architecture, I made hacky, expedient changes:

1. Changed `UI_COLORS["border"]` from `#ff6b9d` to `#333333` -- correct intent, wrong approach
2. Added `scrollbar` and `scrollbar_track` keys to `UI_COLORS` only -- not to `NEXTSTEP_COLORS`
3. Hardcoded scrollbar hover/active colors as hex in `layout.tcss`, then had to scramble to patch them with per-theme CSS overrides
4. Was about to add a `.theme-nextstep Screen { ... }` block to `theme-nextstep.tcss` with more hardcoded hex -- piling hacks on hacks

Each "fix" created a new problem that required another hack. This is the pattern to break.

## The Core Misunderstanding

I treated NeXTSTEP as one optional theme among many. **It is not.** NeXTSTEP is the foundational design language of the entire application. From `CLAUDE.md`:

> The TUI design is heavily inspired by the classic NeXTSTEP user interface. This choice reflects a commitment to "the next step of uniformity".

Every theme -- dark, light, any future color palette -- follows the same NeXTSTEP structural design: beveled borders, zone-based layout, 3D affordances, inset input fields, raised panels. A "theme" is only a color palette swap. The structure is always NeXTSTEP.

## What Exists Now

### Files

| File | Purpose | Problem |
|------|---------|---------|
| `src/tunacode/constants.py` | Theme color palettes + `Theme()` builders | `UI_COLORS` and `NEXTSTEP_COLORS` define different variable sets. Missing shared contract. |
| `src/tunacode/ui/styles/layout.tcss` | Structural layout | Mixes structure with hardcoded scrollbar colors. Uses `$accent` for scrollbar which is a semantic mismatch. |
| `src/tunacode/ui/styles/panels.tcss` | Panel styling | Fine structurally, uses `$variables`. |
| `src/tunacode/ui/styles/widgets.tcss` | StatusBar, mode indicator | Has one hardcoded hex (`#4ec9b0`) for `.mode-active`. |
| `src/tunacode/ui/styles/modals.tcss` | Setup screen | Uses `$variables`, fine. |
| `src/tunacode/ui/styles/theme-nextstep.tcss` | 352 lines of per-theme overrides | **Should not exist.** Its structural rules belong in the base CSS. Its colors belong in theme variables. |

### Current Theme Variable Definitions

**tunacode theme** (`build_tunacode_theme`):
```python
variables={
    "text-muted": p["muted"],
    "border": p["border"],
    "scrollbar-color": p["scrollbar"],      # added by me, only here
    "scrollbar-track": p["scrollbar_track"], # added by me, only here
}
```

**nextstep theme** (`build_nextstep_theme`):
```python
variables={
    "text-muted": p["muted"],
    "border": p["border"],
    "bevel-light": p["bevel_light"],        # only here
    "bevel-dark": p["bevel_dark"],           # only here
    "title-bar": p["title_bar"],             # only here
    "title-bar-text": p["title_bar_text"],   # only here
    "window-content": p["window_content"],   # only here
}
```

These two themes define **completely different variable sets**. That is the root cause. Any CSS that references `$bevel-light` breaks in the dark theme. Any CSS that references `$scrollbar-color` breaks in the light theme.

## The Correct Architecture

### Principle

Every theme provides the **same set of variables**. CSS references only those variables. Zero hardcoded hex in CSS. Zero per-theme CSS override files.

### Shared Variable Contract

Every theme must define at minimum:

```python
variables = {
    # Structural (NeXTSTEP bevels)
    "bevel-light":    "...",  # raised edge highlight
    "bevel-dark":     "...",  # raised edge shadow

    # Borders
    "border":         "...",  # structural borders (viewport, editor)

    # Text
    "text-muted":     "...",  # secondary text

    # Scrollbar
    "scrollbar-thumb": "...", # scrollbar handle
    "scrollbar-track": "...", # scrollbar gutter
}
```

Plus the standard Textual theme properties (`primary`, `accent`, `background`, `surface`, `success`, `warning`, `error`, `foreground`).

### CSS Uses Only Variables

```tcss
/* Raised 3D bevel (NeXTSTEP) */
#viewport {
    border-top: solid $bevel-light;
    border-left: solid $bevel-light;
    border-bottom: solid $bevel-dark;
    border-right: solid $bevel-dark;
}

/* Scrollbar */
Screen {
    scrollbar-color: $scrollbar-thumb;
    scrollbar-background: $scrollbar-track;
}
```

### Delete `theme-nextstep.tcss`

Its 352 lines of hardcoded overrides become unnecessary because:
- Structural rules (beveled borders) move into base CSS using `$bevel-light` / `$bevel-dark`
- Color overrides are handled by the theme variable system automatically
- State overrides (streaming = inverted bevel) use the same variables

### Dream UI Reference Images

Restored to `docs/images/dream-ui/`:
- `tunacode-cli-home.png` -- home screen, subtle gray borders, pink scrollbar
- `tunacode-cli-home-catpu.png` -- same, alternate scrollbar color
- `tunacode-cli-response.png` -- tool calls with cyan accents, agent response
- `tunacode-cli-lsp.png` -- code diff panel with cyan border, LSP diagnostics
- `memory-bank/plan/assets/dream-mockup-slim-panels.webp` -- slim panel variant

Key observations from the mockups:
- Viewport border: subtle dark gray (NOT magenta)
- Scrollbar: signature pink/magenta thumb on dark track
- Streaming mode viewport border: cyan (`$primary`), not magenta (`$accent`)
- Tool panels: cyan border
- Overall: dark background, cyan + magenta accent pair

## Steps To Execute

1. Define the shared variable contract (list of variable names every theme must provide)
2. Update `UI_COLORS` dict to include `bevel_light`, `bevel_dark`, `scrollbar_thumb`, `scrollbar_track`
3. Update `NEXTSTEP_COLORS` dict to include `scrollbar_thumb`, `scrollbar_track` (already has bevels)
4. Update both `build_*_theme()` functions to emit the identical variable set
5. Rewrite base CSS files (`layout.tcss`, `panels.tcss`, `widgets.tcss`) to use the shared variables for NeXTSTEP structural styling (beveled borders everywhere)
6. Delete `theme-nextstep.tcss` entirely
7. Remove it from the `CSS_PATH` list in `app.py` (line ~58)
8. Run tests: `uv run pytest tests/ -x -q`
9. Run lint: `uv run ruff check --fix .`
10. Visual verification: launch the app and switch between themes

## Reference

- NeXTSTEP UI skill: `.claude/skills/neXTSTEP-ui/SKILL.md`
- Original NeXTSTEP guidelines PDF: `.claude/skills/neXTSTEP-ui/NeXTSTEP_User_Interface_Guidelines_Release_3_Nov93.pdf`
- CSS files: `src/tunacode/ui/styles/`
- Theme builders: `src/tunacode/constants.py` lines 111-170
- CSS loading: `src/tunacode/ui/app.py` lines 58-64
