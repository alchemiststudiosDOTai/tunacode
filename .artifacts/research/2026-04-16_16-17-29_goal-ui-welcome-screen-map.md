---
title: "goal ui welcome screen research findings"
link: "goal-ui-welcome-screen-research"
type: research
ontological_relations:
  - relates_to: [[docs/modules/ui/ui]]
  - relates_to: [[docs/ui/css-architecture]]
tags: [research, ui, welcome-screen, textual]
uuid: "40fb4861-1a03-47b1-9959-5e0167756a5b"
created_at: "2026-04-16T16:17:29-05:00"
---

## Scope

User-provided target screenshot shows these visible regions:
- Top bar with model label, percentage, session cost, and `LSP:` indicator.
- Main bordered viewport with fish logo, welcome title, subtitle, command list, and a cache/indexing status line.
- Bottom editor area with `>` prompt.
- Bottom footer/status row with `last:`, branch name, and `edited:`.

This document maps the current repository implementation that owns those areas.

## Structure

- `src/tunacode/ui/app.py:158` composes the visible shell in this order: `ResourceBar`, `#workspace`, `#viewport`, hidden `#context-rail`, `Editor`, file autocomplete, command autocomplete, skills autocomplete.
- `src/tunacode/ui/app.py:167` defines `#workspace` as the horizontal container for the main viewport and the optional context rail.
- `src/tunacode/ui/lifecycle.py:80` starts the REPL, updates the resource bar, and then calls `show_welcome(app.chat_container)`.
- `src/tunacode/ui/welcome.py:41` writes the logo and hardcoded welcome copy into the chat container.
- `src/tunacode/ui/styles/layout.tcss:26` styles the top `ResourceBar`.
- `src/tunacode/ui/styles/layout.tcss:48` styles the main bordered `#viewport`.
- `src/tunacode/ui/styles/layout.tcss:200` styles the bottom `Editor`.
- `src/tunacode/ui/context_panel.py:41` builds the right-side inspector widgets shown when the context panel is toggled on.

## Key Files

- `src/tunacode/ui/welcome.py:31`
  - `WELCOME_TITLE_FORMAT = ">>> {name} v{version}"`
  - `SECTION_DIVIDER = "   ──────────────────────────────────────────────\n\n"`
- `src/tunacode/ui/welcome.py:62`
  - Welcome title and subtitle are rendered from `APP_NAME` and `APP_VERSION`.
- `src/tunacode/ui/welcome.py:68`
  - Hardcoded command rows: `/help`, `/clear`, `/resume`.
- `src/tunacode/ui/welcome.py:77`
  - Hardcoded command rows: `/model`, `/theme`.
- `src/tunacode/ui/welcome.py:84`
  - Hardcoded command rows: `!<cmd>`, `/thoughts`, `ctrl+y`.
- `src/tunacode/ui/welcome.py:93`
  - Hardcoded slopgotchi copy mentioning the context panel and `ctrl+e`.

- `src/tunacode/ui/logo_assets.py:7`
  - Welcome logo asset name is `logo.ansi`.
- `src/tunacode/ui/logo_assets.py:13`
  - `read_logo_ansi()` loads the asset from `tunacode.ui/assets`.
- `src/tunacode/ui/assets/logo.ansi`
  - Asset file exists.
  - Local inspection found `9` lines and maximum plain-text width `32`.

- `src/tunacode/ui/app.py:159`
  - `self.resource_bar = ResourceBar()`
- `src/tunacode/ui/app.py:160`
  - `self.chat_container = ChatContainer(id="chat-container", auto_scroll=True)`
- `src/tunacode/ui/app.py:165`
  - `self.editor = Editor()`
- `src/tunacode/ui/app.py:174`
  - Context rail starts with class `hidden`.
- `src/tunacode/ui/app.py:177`
  - Context rail border title is `"Session Inspector"`.
- `src/tunacode/ui/app.py:603`
  - `action_toggle_context_panel()` toggles the context rail.
- `src/tunacode/ui/app.py:616`
  - `on_resize()` hides the context rail below the minimum supported width.

- `src/tunacode/ui/widgets/resource_bar.py:22`
  - `ResourceBar` is the top-row widget.
- `src/tunacode/ui/widgets/resource_bar.py:101`
  - `_refresh_display()` assembles the visible content.
- `src/tunacode/ui/widgets/resource_bar.py:111`
  - Base parts are circle glyph, remaining percentage, separator, model, separator, session cost.
- `src/tunacode/ui/widgets/resource_bar.py:120`
  - Optional LSP segment appends `server_name` and a status glyph.
- `src/tunacode/ui/widgets/resource_bar.py:127`
  - Optional compaction segment appends `Compacting...`.

- `src/tunacode/ui/app.py:742`
  - `_update_resource_bar()` reads session model, estimated tokens, max tokens, and session cost.
- `src/tunacode/ui/app.py:753`
  - `_update_resource_bar()` pushes those values into `ResourceBar.update_stats(...)`.
- `src/tunacode/ui/app.py:795`
  - `update_lsp_for_file()` updates the resource bar LSP indicator.

- `src/tunacode/ui/widgets/editor.py:62`
  - `Editor()` initializes with `placeholder=">"`.
- `src/tunacode/ui/styles/layout.tcss:200`
  - `Editor` width is `1fr`, height is `6`, and it has a bordered inset-style box.

- `src/tunacode/ui/context_panel.py:41`
  - `build_context_panel_widgets()` creates fields for pet, model, context, cost, files, and loaded skills.
- `src/tunacode/ui/context_panel.py:47`
  - Pet field border title uses `SLOPGOTCHI_NAME`.
- `src/tunacode/ui/context_panel.py:82`
  - Skills field border title is `"Loaded Skills"`.
- `src/tunacode/ui/app.py:645`
  - `_refresh_context_panel()` updates model, context gauge, cost, files, and skills content.

- `src/tunacode/constants.py:20`
  - `APP_NAME = "TunaCode"`
- `src/tunacode/constants.py:21`
  - `APP_VERSION = "0.2.0"`
- `src/tunacode/constants.py:70`
  - `UI_COLORS` defines the default TunaCode dark palette.
- `src/tunacode/constants.py:113`
  - Default theme name is `tunacode`.
- `src/tunacode/constants.py:247`
  - Resource bar separator is `" - "`.
- `src/tunacode/constants.py:265`
  - `build_tunacode_theme()` constructs the default theme from `UI_COLORS`.

## Patterns Found

- Hardcoded welcome content:
  - `src/tunacode/ui/welcome.py:62`
  - `src/tunacode/ui/welcome.py:68`
  - `src/tunacode/ui/welcome.py:77`
  - `src/tunacode/ui/welcome.py:84`
  - `src/tunacode/ui/welcome.py:93`

- Welcome path writes into the chat log rather than a dedicated home-screen widget:
  - `src/tunacode/ui/lifecycle.py:95`
  - `src/tunacode/ui/lifecycle.py:97`
  - `src/tunacode/ui/app.py:160`

- Top-bar content is assembled in code, not CSS:
  - `src/tunacode/ui/widgets/resource_bar.py:101`
  - `src/tunacode/ui/app.py:742`
  - `src/tunacode/ui/app.py:795`

- Layout structure is split between compose order and TCSS:
  - `src/tunacode/ui/app.py:158`
  - `src/tunacode/ui/styles/layout.tcss:26`
  - `src/tunacode/ui/styles/layout.tcss:40`
  - `src/tunacode/ui/styles/layout.tcss:48`
  - `src/tunacode/ui/styles/layout.tcss:64`
  - `src/tunacode/ui/styles/layout.tcss:200`

- Context rail is hidden by default and uses `ctrl+e` for visibility control:
  - `src/tunacode/ui/app.py:101`
  - `src/tunacode/ui/app.py:174`
  - `src/tunacode/ui/app.py:603`

## Command Surface

- Registered slash commands are defined in `src/tunacode/ui/command_registry.py:21`:
  - `help`
  - `cancel`
  - `clear`
  - `compact`
  - `debug`
  - `exit`
  - `model`
  - `resume`
  - `skills`
  - `theme`
  - `thoughts`
  - `update`

- Command routing is in `src/tunacode/ui/commands/__init__.py:19`:
  - `!` routes to shell command execution.
  - `/` routes to registered slash commands.
  - bare `exit` exits the app.

- Repository text search returned no matches under `src/tunacode` for:
  - `/plan`
  - `/yolo`
  - `/branch`
  - `Code cache built`
  - `last:`
  - `edited:`

## Dependencies

- REPL startup to welcome render:
  - `src/tunacode/ui/lifecycle.py:80` `_start_repl()`
  - `src/tunacode/ui/lifecycle.py:93` `app._update_resource_bar()`
  - `src/tunacode/ui/lifecycle.py:95` import `show_welcome`
  - `src/tunacode/ui/lifecycle.py:97` `show_welcome(app.chat_container)`

- Welcome render to logo asset:
  - `src/tunacode/ui/welcome.py:35` `generate_logo()`
  - `src/tunacode/ui/welcome.py:41` `show_welcome(...)`
  - `src/tunacode/ui/logo_assets.py:13` `read_logo_ansi(...)`
  - `src/tunacode/ui/assets/logo.ansi`

- Resource bar update path:
  - `src/tunacode/ui/app.py:742` `_update_resource_bar()`
  - `src/tunacode/ui/widgets/resource_bar.py:39` `update_stats(...)`
  - `src/tunacode/ui/widgets/resource_bar.py:60` `update_lsp_status(...)`
  - `src/tunacode/ui/widgets/resource_bar.py:71` `update_compaction_status(...)`

- Context panel update path:
  - `src/tunacode/ui/app.py:645` `_refresh_context_panel()`
  - `src/tunacode/ui/context_panel.py:120` `build_context_gauge(...)`
  - `src/tunacode/ui/context_panel.py:140` `build_files_field(...)`
  - `src/tunacode/ui/context_panel.py:158` `build_skills_field(...)`

## Documentation References

- UI module docs describe the resource bar and a bottom status bar:
  - `docs/modules/ui/ui.md:58`
  - `docs/modules/ui/ui.md:59`

- UI module docs also describe the status bar as a 3-zone layout:
  - `docs/modules/ui/ui.md:321`
  - `docs/modules/ui/ui.md:322`
  - `docs/modules/ui/ui.md:323`
  - `docs/modules/ui/ui.md:324`

- CSS architecture docs list `widgets.tcss` as owning a status bar and show a zone layout with a footer row:
  - `docs/ui/css-architecture.md:18`
  - `docs/ui/css-architecture.md:22`
  - `docs/ui/css-architecture.md:112`
  - `docs/ui/css-architecture.md:125`

- Current widget file listing under `src/tunacode/ui/widgets/` contains:
  - `chat.py`
  - `command_autocomplete.py`
  - `editor.py`
  - `file_autocomplete.py`
  - `messages.py`
  - `resource_bar.py`
  - `skills_autocomplete.py`
  - No `status_bar.py` file is present in the current widget directory listing.

## Symbol Index

- `src/tunacode/ui/app.py:80` `TextualReplApp`
- `src/tunacode/ui/welcome.py:35` `generate_logo`
- `src/tunacode/ui/welcome.py:41` `show_welcome`
- `src/tunacode/ui/widgets/resource_bar.py:22` `ResourceBar`
- `src/tunacode/ui/widgets/editor.py:45` `Editor`
- `src/tunacode/ui/context_panel.py:24` `InspectorField`
- `src/tunacode/ui/context_panel.py:31` `ContextPanelWidgets`
- `src/tunacode/ui/context_panel.py:41` `build_context_panel_widgets`
- `src/tunacode/ui/context_panel.py:120` `build_context_gauge`
- `src/tunacode/ui/context_panel.py:140` `build_files_field`
- `src/tunacode/ui/context_panel.py:158` `build_skills_field`
- `src/tunacode/ui/command_registry.py:14` `CommandSpec`
- `src/tunacode/ui/command_registry.py:49` `LazyCommandRegistry`
- `src/tunacode/constants.py:265` `build_tunacode_theme`
- `src/tunacode/constants.py:290` `build_nextstep_theme`
