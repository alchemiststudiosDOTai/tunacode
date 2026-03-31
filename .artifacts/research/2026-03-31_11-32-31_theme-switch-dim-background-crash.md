---
title: "theme switch dim-background crash research findings"
link: "theme-switch-dim-background-crash-research"
type: research
ontological_relations:
  - relates_to: [[docs/ui/css-architecture]]
tags: [research, ui, themes, textual]
uuid: "4b86b09f-08be-49b9-bda8-d4c0713aa48a"
created_at: "2026-03-31T11:32:31-05:00"
---

## Scope

Research target: the theme-switch crash reported from the installed CLI while a user was changing themes.

## Input Evidence

User-supplied traceback references:
- `/home/fabian/.local/share/uv/tools/tunacode-cli/lib/python3.13/site-packages/textual/filter.py:255`
- `/home/fabian/.local/share/uv/tools/tunacode-cli/lib/python3.13/site-packages/textual/filter.py:142`

User-supplied traceback values:
- `style = Style(color=Color('default', ColorType.DEFAULT), bgcolor=Color('default', ColorType.DEFAULT), dim=True, meta={'offset': (0, 1)})`
- `background = Color('default', ColorType.DEFAULT)`
- `bgcolor = Color('#f7f7f7', ColorType.TRUECOLOR, triplet=ColorTriplet(red=247, green=247, blue=247))`
- `color = Color('#000000', ColorType.TRUECOLOR, triplet=ColorTriplet(red=0, green=0, blue=0))`
- exception site: `red1, green1, blue1 = background.triplet`

## Theme Switching Structure

- `src/tunacode/ui/app.py:120-124` registers TunaCode, NeXTSTEP, and wrapped built-in themes, then sets `self.theme = THEME_NAME`.
- `src/tunacode/constants.py:113-114` defines the custom theme names `tunacode` and `nextstep`.
- `src/tunacode/constants.py:118-207` defines the built-in palette wrappers, including `catppuccin-latte`, `solarized-light`, `textual-light`, `textual-dark`, and `tokyo-night`.
- `src/tunacode/constants.py:217-220` defines `SUPPORTED_THEME_NAMES` as `tunacode`, `nextstep`, and all names from `BUILTIN_THEME_PALETTES`.
- `src/tunacode/ui/app.py:195-199` exposes `supported_themes` by filtering `available_themes` through `SUPPORTED_THEME_NAMES`.
- `src/tunacode/ui/commands/theme.py:23-32` applies a direct `/theme <name>` change via `app.theme = theme_name` and persists `settings.theme`.
- `src/tunacode/ui/commands/theme.py:37-49` opens `ThemePickerScreen` when `/theme` is invoked with no argument.
- `src/tunacode/ui/screens/theme_picker.py:74-80` sets the initial highlight and applies live preview on highlight changes via `self.app.theme = str(event.option.id)`.
- `src/tunacode/ui/screens/theme_picker.py:87-90` restores the original theme on cancel.
- `docs/ui/css-architecture.md:95` states that the theme picker has live preview and that ESC reverts to the original.

## Theme Object Construction

- `src/tunacode/constants.py:87-100` defines the `NEXTSTEP_COLORS` palette with `background="#acacac"`, `surface="#c8c8c8"`, and `text="#000000"`.
- `src/tunacode/constants.py:293-318` rebuilds built-in Textual themes in `_wrap_builtin_theme` by copying properties from the original theme.
- `src/tunacode/constants.py:311-314` copies `foreground`, `background`, `surface`, and `panel` with `getattr(theme, ..., None)`.
- `src/tunacode/constants.py:323-332` wraps any built-in theme present in `available_themes` and returns the wrapped list.

## Render Path Carrying `dim=True`

- `src/tunacode/ui/renderers/tools/base.py:112-115` builds the hook prefix and appends `HOOK_ARROW_PREFIX` with `style="dim"`.
- `src/tunacode/ui/renderers/tools/base.py:123` appends the relative path with `style="dim underline"`.
- Additional renderers in the UI use `dim` styles in rendered Rich content, including:
  - `src/tunacode/ui/renderers/agent_response.py:58,84`
  - `src/tunacode/ui/renderers/search.py:140,147,160,162-165`
  - `src/tunacode/ui/renderers/tools/read_file.py:192,206,263`
  - `src/tunacode/ui/renderers/tools/web_fetch.py:87,96-100,138,178`

## Chat Widget / Selection Path

- `src/tunacode/ui/widgets/chat.py:29-40` defines `SelectableRichVisual`.
- `src/tunacode/ui/widgets/chat.py:40-132` re-renders Rich content into segments and injects `meta={"offset": (x, y)}` into segment styles.
- `src/tunacode/ui/widgets/chat.py:66-69` builds the replacement Rich style by adding only offset metadata to the existing segment style.
- `src/tunacode/ui/widgets/chat.py:184-202` defines `CopyOnSelectStatic._render()` and replaces `RichVisual` with `SelectableRichVisual`.
- `src/tunacode/ui/widgets/chat.py:268-283` shows `ChatContainer.write()` creating a `CopyOnSelectStatic` for chat content.

## Textual Filter Path Reached by Theme Changes

Installed CLI environment paths below match the traceback path prefix `/home/fabian/.local/share/uv/tools/tunacode-cli/lib/python3.13/site-packages/textual/`.

- `app.py:536-539` defines `ansi_theme_dark = MONOKAI` and `ansi_theme_light = ALABASTER`.
- `app.py:583-584` installs `ANSIToTruecolor(ansi_theme, enabled=not ansi_color)` into `self._filters`.
- `app.py:1398-1405` returns `ansi_theme_dark` for dark themes and `ansi_theme_light` for light themes via `App.ansi_theme`.
- `app.py:1408-1417` replaces the `ANSIToTruecolor` filter when the app theme changes.
- `_styles_cache.py:125` retrieves `base_background, background = widget._opacity_background_colors`.
- `_styles_cache.py:250` applies each enabled filter with `strip = strip.apply_filter(filter, background)`.
- `_styles_cache.py:323-324` sets `inner = Style(background=(base_background + background))` and `outer = Style(background=base_background)` while rendering styled lines.
- `filter.py:220-255` defines `ANSIToTruecolor.truecolor_style()`.
- `filter.py:254-255` calls `color = dim_color(background, color)` when `style.dim` is true and `color` is not `None`.
- `filter.py:129-142` defines `dim_color()` and unpacks `background.triplet` at line 142.

## ANSI Theme Values Matching the Traceback

- `/home/fabian/.local/share/uv/tools/tunacode-cli/lib/python3.13/site-packages/textual/_ansi_theme.py:47-49` defines `ALABASTER = TerminalTheme(rgb(247, 247, 247), rgb(0, 0, 0), ...)`.
- The user-supplied traceback values `bgcolor=#f7f7f7` and `color=#000000` match `ALABASTER`'s first two RGB values at `_ansi_theme.py:48-49`.
- `App.ansi_theme` switches to `ansi_theme_light` for any light theme at `app.py:1398-1405`.

## Runtime Inspection Findings

Executed locally in the repo virtual environment (`uv run python`) and in the installed CLI tool environment.

### Installed CLI tool environment

Command outcome:
- `/home/fabian/.local/share/uv/tools/tunacode-cli/bin/python - <<'PY' ... print(textual.__version__) ... PY`
- reported `textual==4.0.0`
- executable path reported `/home/fabian/.local/share/uv/tools/tunacode-cli/bin/python`

### Repo virtual environment

Command outcome:
- `uv run python - <<'PY' ... print(textual.__version__) ... PY`
- reported `textual==4.0.0`

### Theme object values from `TextualReplApp.supported_themes`

Local inspection showed:
- `nextstep`: `foreground=#000000`, `background=#acacac`, `surface=#c8c8c8`
- `textual-light`: `foreground=None`, `background=#E0E0E0`, `surface=#D8D8D8`, `panel=#D0D0D0`
- `textual-dark`: `foreground=#e0e0e0`, `background=None`, `surface=None`, `panel=None`
- `catppuccin-latte`: `foreground=#4C4F69`, `background=#EFF1F5`, `surface=#E6E9EF`
- `solarized-light`: `foreground=#586e75`, `background=#fdf6e3`, `surface=#eee8d5`

## Reproduction Attempts

The following local scripted runs completed without raising the traceback exception:

1. `TextualReplApp.run_test()` with a chat message containing `Text()` segments styled as `dim` and repeated `app.theme = ...` assignments through light themes (`nextstep`, `textual-light`, `catppuccin-latte`, `solarized-light`).
2. `TextualReplApp.run_test()` with `ChatContainer.write()` content mounted as plain chat content, `user-message`, `tool-panel`, `agent-panel`, and `thinking-panel`, followed by repeated theme changes.
3. `TextualReplApp.run_test()` opening `ThemePickerScreen` and sending repeated `down` keypresses to trigger live preview changes through the picker.
4. A minimal standalone Textual `App` with a `Static(Text(..., style='dim'))` and repeated theme changes through light themes.

Observed result for all four runs: no exception was raised locally.

## File Map

- `src/tunacode/ui/app.py:118-124` → theme registration during app construction
- `src/tunacode/constants.py:87-100` → NeXTSTEP palette values
- `src/tunacode/constants.py:118-220` → built-in theme wrapper palette list and supported names
- `src/tunacode/constants.py:293-318` → built-in theme re-wrapping logic
- `src/tunacode/ui/commands/theme.py:23-49` → direct theme changes and picker launch
- `src/tunacode/ui/screens/theme_picker.py:74-90` → live preview and cancel/revert path
- `src/tunacode/ui/widgets/chat.py:29-132` → selectable Rich visual and segment metadata injection
- `src/tunacode/ui/widgets/chat.py:184-202` → `CopyOnSelectStatic` Rich visual substitution
- `src/tunacode/ui/widgets/chat.py:268-283` → chat widget creation path
- `/home/fabian/.local/share/uv/tools/tunacode-cli/lib/python3.13/site-packages/textual/app.py:536-584,1398-1417` → ANSI theme selection and filter refresh
- `/home/fabian/.local/share/uv/tools/tunacode-cli/lib/python3.13/site-packages/textual/_styles_cache.py:125,250,323-324` → filter application inputs
- `/home/fabian/.local/share/uv/tools/tunacode-cli/lib/python3.13/site-packages/textual/filter.py:129-142,220-255` → failing `dim_color` path
- `/home/fabian/.local/share/uv/tools/tunacode-cli/lib/python3.13/site-packages/textual/_ansi_theme.py:47-49` → ALABASTER light ANSI theme values
