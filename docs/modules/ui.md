---
title: UI Layer
summary: Textual-based TUI application, custom widgets, tool renderers, modal screens, and theming.
read_when: Modifying the terminal interface, adding a new widget, changing how tool output is displayed, or adjusting themes.
depends_on: [types, core, configuration]
feeds_into: []
---

# UI Layer

**Package:** `src/tunacode/ui/`

## What

The user-facing terminal interface built on [Textual](https://textual.textualize.io/). Owns the REPL loop, input handling, streaming display, tool result panels, modal screens, and theming. Follows NeXTSTEP design principles (uniformity, user-informed, professional clarity).

## Key Files

### Application Shell

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point via Typer. `_default_command()` launches the TUI. `run_headless()` runs non-interactive mode. Handles `--model`, `--baseurl`, `--setup`, `--version` flags. |
| `app.py` | `TextualReplApp(App)` -- the Textual application. `compose()` builds the widget tree: `ResourceBar`, `ChatContainer`, `LoadingIndicator`, `Editor`, `FileAutoComplete`, `CommandAutoComplete`, `StatusBar`. `_process_request()` calls `process_request()` from core and manages the streaming/rendering lifecycle. |
| `repl_support.py` | Callback factories: `build_textual_tool_callback()`, `build_tool_result_callback()`, `build_tool_start_callback()`. `format_user_message()` renders user input blocks. `run_textual_repl()` starts the Textual app. |
| `shell_runner.py` | `ShellRunner` -- executes shell commands within the TUI context (for `!command` support). |
| `welcome.py` | `show_welcome()` -- renders the startup banner in the chat container. |
| `logo_assets.py` | ASCII art logo data. |
| `clipboard.py` | System clipboard integration. |
| `model_display.py` | Model name formatting for the resource bar. |
| `styles.py` | Style constants (`STYLE_PRIMARY`, `STYLE_WARNING`, etc.). |

### Widgets (`widgets/`)

| File | Purpose |
|------|---------|
| `chat.py` | `ChatContainer` -- scrollable message history with panel support and insertion anchors. |
| `editor.py` | `Editor` -- multi-line input with submit event (`EditorSubmitRequested`). |
| `resource_bar.py` | `ResourceBar` -- top bar showing model, token usage, cost, compaction status, LSP status. |
| `status_bar.py` | `StatusBar` -- bottom bar showing running/last action. |
| `command_autocomplete.py` | `CommandAutoComplete` -- slash-command completion overlay. |
| `file_autocomplete.py` | `FileAutoComplete` -- file path completion overlay. |
| `messages.py` | `ToolResultDisplay` message class -- carries tool output from callback to app for rendering. |

### Renderers (`renderers/`)

| File | Purpose |
|------|---------|
| `agent_response.py` | Formats final agent response with token count and duration. |
| `errors.py` | `render_exception()` -- formats any exception into a Rich renderable with panel metadata. |
| `panels.py` | `tool_panel_smart()` -- builds tool output panels with adaptive width. |
| `panel_widths.py` | Width calculation logic for tool panels. |
| `search.py` | Search result rendering. |

### Tool Renderers (`renderers/tools/`)

One renderer per tool type:

| File | Renders |
|------|---------|
| `base.py` | Base tool renderer protocol. |
| `bash.py` | Shell command output with exit code. |
| `glob.py` | File match lists. |
| `grep.py` | Search results with context lines. |
| `list_dir.py` | Directory listings. |
| `read_file.py` | File contents with syntax highlighting. |
| `update_file.py` | Diff-style before/after display. |
| `write_file.py` | File creation confirmation. |
| `web_fetch.py` | Fetched URL content. |
| `diagnostics.py` | LSP diagnostic output. |
| `syntax_utils.py` | Syntax highlighting helpers shared across renderers. |

### Screens (`screens/`)

Modal screens pushed on top of the main app:

| File | Screen | Trigger |
|------|--------|---------|
| `setup.py` | `SetupScreen` | First run or `--setup` flag. |
| `model_picker.py` | `ModelPickerScreen` | `/model` command. |
| `session_picker.py` | `SessionPickerScreen` | `/session` command. |
| `theme_picker.py` | `ThemePickerScreen` | `/theme` command. |
| `update_confirm.py` | `UpdateConfirmScreen` | When a new version is detected. |

### Commands (`commands/`)

| File | Purpose |
|------|---------|
| `base.py` | `handle_command()` dispatcher -- routes `/compact`, `/clear`, `/model`, etc. |
| `compact.py` | `/compact` command implementation. |

### Escape Handling (`esc/`)

| File | Purpose |
|------|---------|
| `handler.py` | `EscHandler` -- prioritized escape: cancel request > kill shell > clear editor. |
| `types.py` | Escape action enum. |

### Headless (`headless/`)

| File | Purpose |
|------|---------|
| `output.py` | `resolve_output()` -- extracts the final response text for non-interactive mode. |

### Styles

CSS files in `ui/styles/`:

| File | Purpose |
|------|---------|
| `layout.tcss` | Main layout grid. |
| `widgets.tcss` | Widget-specific styles. |
| `modals.tcss` | Modal screen styles. |
| `panels.tcss` | Tool panel styles. |

### Core-UI Bridge (`core/ui_api/`)

Thin adapters that let core expose UI-relevant data without importing Textual:

| File | Purpose |
|------|---------|
| `configuration.py` | `ApplicationSettings` for UI consumers. |
| `constants.py` | UI constants re-exported from `tunacode.constants` (themes, sizing, version). |
| `file_filter.py` | File filtering for autocomplete. |
| `formatting.py` | Text formatting for display. |
| `lsp_status.py` | LSP availability info for resource bar. |
| `messaging.py` | `estimate_messages_tokens()`, `get_content()` -- message introspection without importing agent internals. |
| `shared_types.py` | `ModelName` and other types used by both core and UI. |
| `system_paths.py` | `get_project_id()`, `check_for_updates()`. |
| `user_configuration.py` | User config access for UI screens. |

## How

### Widget Tree

```
TextualReplApp
  +-- ResourceBar              (model / tokens / cost / compaction / LSP)
  +-- Container#viewport
  |     +-- ChatContainer      (scrollable message history)
  |     +-- LoadingIndicator   (spinner during requests)
  +-- Static#streaming-output  (live streaming text)
  +-- Editor                   (multi-line input)
  +-- FileAutoComplete         (overlay)
  +-- CommandAutoComplete      (overlay)
  +-- StatusBar                (bottom bar)
```

### Request Display Flow

1. User submits text in `Editor` -> `EditorSubmitRequested` event.
2. `on_editor_submit_requested()` checks for slash commands, then enqueues the message.
3. `_request_worker()` dequeues and calls `_process_request()`.
4. During streaming: `_streaming_callback()` accumulates text deltas into `Static#streaming-output`.
5. On tool results: `ToolResultDisplay` message -> `on_tool_result_display()` -> `tool_panel_smart()` renders a Rich panel.
6. After completion: streaming output is cleared, final response is rendered as markdown in `ChatContainer`.

## Why

The UI layer has zero knowledge of tinyagent, message formats, or provider APIs. It communicates with core exclusively through `process_request()` and callbacks. The `core/ui_api/` bridge ensures this boundary stays clean.

NeXTSTEP design principles drive the aesthetic: beveled panels, monochrome variants, status-bar-driven feedback, uniform widget spacing. The custom theme system (`build_tunacode_theme()`, `build_nextstep_theme()`, `wrap_builtin_themes()`) ensures every Textual built-in theme also gets the six contract CSS variables (`bevel-light`, `bevel-dark`, `border`, `text-muted`, `scrollbar-thumb`, `scrollbar-track`).
