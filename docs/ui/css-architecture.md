# CSS Architecture

## Design Language

Every theme follows the NeXTSTEP structural design: beveled borders, zone-based layout, 3D affordances, inset input fields, raised panels. A "theme" swaps only the color palette. The structure is always NeXTSTEP.

## File Layout

```
src/tunacode/ui/styles/
  layout.tcss    Screen, ResourceBar, viewport, streaming-output, Editor
  panels.tcss    Chat message panels (agent, tool, error, search, etc.)
  widgets.tcss   StatusBar (3-column bottom bar)
  modals.tcss    SetupScreen modal
```

Four files. No per-theme override files. `app.py` loads them via `CSS_PATH`:

```python
CSS_PATH = [
    "styles/layout.tcss",
    "styles/widgets.tcss",
    "styles/modals.tcss",
    "styles/panels.tcss",
]
```

## Theme Variable Contract

Every theme must provide exactly 6 CSS variables. The contract lives in `src/tunacode/constants.py` as `THEME_VARIABLE_CONTRACT`:

| CSS Variable        | Palette Key        | Purpose                       |
|---------------------|--------------------|-------------------------------|
| `$bevel-light`      | `bevel_light`      | Raised edge highlight (top/left) |
| `$bevel-dark`       | `bevel_dark`       | Raised edge shadow (bottom/right) |
| `$border`           | `border`           | Structural borders             |
| `$text-muted`       | `muted`            | Secondary/dim text             |
| `$scrollbar-thumb`  | `scrollbar_thumb`  | Scrollbar handle color         |
| `$scrollbar-track`  | `scrollbar_track`  | Scrollbar gutter color         |

Plus Textual's built-in theme properties: `primary`, `accent`, `background`, `surface`, `success`, `warning`, `error`, `foreground`.

`_build_theme_variables()` validates that every palette provides all required keys. Missing keys cause a hard crash at startup -- fail fast, fail loud.

## Palettes

### Custom Palettes

Two palettes defined as dicts in `constants.py`:

- **`UI_COLORS`** -- High-contrast dark scheme. Cyan + magenta accent pair. Default theme.
- **`NEXTSTEP_COLORS`** -- Classic 1990s NeXTSTEP light gray. Pure monochrome.

Both define the same set of keys. Both are built into Textual `Theme` objects via `build_tunacode_theme()` and `build_nextstep_theme()`.

### Built-in Theme Wrapping

`BUILTIN_THEME_PALETTES` provides the 6 contract keys for 12 Textual built-in themes:

catppuccin-latte, catppuccin-mocha, dracula, flexoki, gruvbox, monokai, nord, solarized-light, textual-ansi, textual-dark, textual-light, tokyo-night

At startup, `wrap_builtin_themes()` takes each built-in theme, merges the contract variables on top of its existing variables, and re-registers it. This means every theme in the picker emits the same variable schema.

**Total: 14 supported themes.**

## Rules

1. **Zero hardcoded hex in TCSS.** Every color reference is a `$variable` or a Textual built-in token (`$primary`, `$surface`, etc.).
2. **No per-theme CSS files.** Structure is shared. Palette swaps happen through the variable contract.
3. **Bevel grammar is universal.** Raised = light top/left, dark bottom/right. Pressed/inset = inverted. Streaming viewport uses pressed bevel + `$primary` outline. Paused viewport uses raised bevel + `$warning` outline.
4. **Semantic outlines on panels.** All panels share one structural bevel. The `outline` property carries the semantic color: `$primary` for tools, `$accent` for agent, `$error` for errors, `$success` for completed, `$warning` for warnings.
5. **Tinted backgrounds for depth.** Semantic panels apply a subtle `tint` (4-8%) matching their outline color. This creates visual weight differentiation -- panels aren't just outlined, they glow faintly with their semantic color. Tool running/failed states use higher tint (8%) for urgency.
6. **Transitions on state changes.** Viewport and panels use `transition: tint 250-300ms in_out_cubic` so state changes (idle to streaming, tool running to completed) animate smoothly instead of snapping.
7. **Focus feedback on input.** `Editor:focus-within` shows a `$primary` outline so the user always knows when the input area is active. Bash mode overrides with `$success`.

## Rich Style Constants

`src/tunacode/ui/styles.py` provides Rich-compatible style strings for non-CSS contexts (Rich Text objects, renderables):

```python
STYLE_PRIMARY   = UI_COLORS["primary"]    # "#00d7d7"
STYLE_ACCENT    = UI_COLORS["accent"]     # "#ff6b9d"
STYLE_SUCCESS   = UI_COLORS["success"]    # "#4ec9b0"
STYLE_WARNING   = UI_COLORS["warning"]    # "#c3e88d"
STYLE_ERROR     = UI_COLORS["error"]      # "#f44747"
STYLE_MUTED     = UI_COLORS["muted"]      # "#808080"
STYLE_HEADING   = "bold #ff6b9d"
STYLE_SUBHEADING = "bold #00d7d7"
```

These reference `UI_COLORS` directly. They are used by renderers and the welcome screen -- anywhere Rich text is composed outside of Textual CSS.

## Theme Picker

`src/tunacode/ui/screens/theme_picker.py` -- modal with live preview. Navigating the list swaps the theme in real time. ESC reverts to the original.

## Zone Layout

```
 ResourceBar          (1 row, no border, $background)
+-bevel-light---------+
|  #viewport          |  (1fr, $surface, raised bevel)
|  +- ChatContainer --+
|  |  RichLog         |  (1fr, $background, scrollbar-gutter: stable)
|  +------------------+
|  LoadingIndicator   |  (hidden unless .active)
+-bevel-dark----------+
 #streaming-output     (auto height, hidden unless .active, raised bevel)
+-bevel-dark----------+
|  Editor             |  (6 rows, $background, inset bevel)
+-bevel-light---------+
 StatusBar             (2 rows: 1 bevel + 1 content, $background)
```

The viewport is "raised" (light top/left, dark bottom/right). The editor is "inset" (dark top/left, light bottom/right). This follows NeXTSTEP conventions: display areas are raised, input areas are sunken.
