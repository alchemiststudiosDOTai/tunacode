---
title: UI Layer
summary: Textual-based TUI application, screens, widgets, renderers, command system, and user interaction handling.
read_when: Modifying the REPL interface, adding new commands, styling components, or changing user interaction patterns.
depends_on: [types, infrastructure, core, configuration]
feeds_into: []
---

# UI Layer

**Package:** `src/tunacode/ui/`

## What

The Textual-based terminal user interface for TunaCode. Handles all user interaction, screen navigation, command routing, and rendering of agent responses, tool outputs, and errors. The UI layer consumes the core agent loop and provides a clean, NeXTSTEP-inspired visual experience.

## Key Files

### Application Entry Point

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point using typer. Handles `--setup`, `--model`, `--baseurl` flags, headless mode (`tunacode run`), and launches the TUI. |
| `app.py` | `TextualReplApp` — the main Textual application. Manages request queue, streaming callbacks, tool result display, ESC handler, and composes all widgets. |

### REPL Support & Callbacks

| File | Purpose |
|------|---------|
| `repl_support.py` | Helper functions and callback builders for the REPL. `run_textual_repl()` creates and runs the app. Callback builders wire core events to UI components. |
| `shell_runner.py` | `ShellRunner` — async shell command execution for `!cmd` syntax. Handles timeouts, cancellation (SIGINT), and formats output via NeXTSTEP panels. |

### Screens (Modal Dialogs)

| File | Purpose |
|------|---------|
| `screens/setup.py` | First-time configuration wizard for provider, model, and API key selection. |
| `screens/model_picker.py` | Two-step model selection: `ProviderPickerScreen` → `ModelPickerScreen`. Supports filtering and displays pricing. |
| `screens/session_picker.py` | Session resumption modal with message preview. Lists sessions by ID, model, and last modified date. |
| `screens/theme_picker.py` | Theme selection modal for switching between tunacode, nextstep, and builtin themes. |
| `screens/update_confirm.py` | Confirmation dialog before installing package updates. |

### Widgets (Reusable Components)

| File | Purpose |
|------|---------|
| `widgets/chat.py` | `ChatContainer` — scrollable chat history with insertion point tracking. `CopyOnSelectStatic` enables mouse selection copy. `SelectableRichVisual` injects offset metadata for selection. |
| `widgets/editor.py` | `Editor` — enhanced single-line input with Enter-submit, bash-mode (`!` prefix), paste buffer for multiline input, and custom rendering. |
| `widgets/resource_bar.py` | Top status bar displaying token usage percentage, model name, session cost, LSP server status, and compaction activity. |
| `widgets/status_bar.py` | Bottom status bar with 3 zones: git branch/location (left), edited files (mid), last action (right). |
| `widgets/command_autocomplete.py` | Slash-command auto-completion for the editor. |
| `widgets/file_autocomplete.py` | File path auto-completion for the editor. |

### Renderers (Rich Panel System)

| File | Purpose |
|------|---------|
| `renderers/panels.py` | `RichPanelRenderer` — base renderer for tool panels, error panels, search results, and info panels. `PanelMeta` defines CSS styling and border titles. |
| `renderers/agent_response.py` | Renders finalized agent responses as NeXTSTEP-style panels with markdown content and throughput stats. |
| `renderers/errors.py` | Renders exceptions with severity mapping, suggested fixes, recovery commands, and extracted context fields. |
| `renderers/search.py` | Renders file/code search results with pagination and indexing status. |
| `renderers/tools/` | Tool-specific renderers for bash, grep, glob, list_dir, read_file, update_file, web_fetch, diagnostics. Apply syntax highlighting and truncation. |

### Command System

| File | Purpose |
|------|---------|
| `commands/base.py` | `Command` abstract base class defining the command interface. |
| `commands/__init__.py` | Slash command implementations: `/help`, `/clear`, `/compact`, `/debug`, `/model`, `/theme`, `/resume`, `/update`. Routing via `handle_command()`. |
| `commands/compact.py` | `/compact` command for manual context compaction. Forces summarization of old messages. |

### ESC Key Handling

| File | Purpose |
|------|---------|
| `esc/handler.py` | `EscHandler` — centralized ESC key logic. Priority order: cancel request → cancel shell → clear editor input/paste buffer. |
| `esc/types.py` | Protocol definitions for editor and shell runner injection. |

### Utilities

| File | Purpose |
|------|---------|
| `clipboard.py` | System clipboard integration for copying selected text. |
| `model_display.py` | Model name formatting for the resource bar (truncates long model IDs). |
| `styles.py` | Color constants for UI components (`STYLE_PRIMARY`, `STYLE_WARNING`, etc.). |
| `welcome.py` | Welcome message rendered on fresh REPL start. |
| `headless/output.py` | Headless mode output resolution from agent responses. |
| `logo_assets.py` | ASCII logo assets for the TUI. |

## How

### Application Startup Flow

```
tunacode (CLI)
    |
    v
main.py typer app
    |
    v
_apply_base_url_override()  (if --baseurl)
    |
    v
_run_textual_cli()
    |
    v
TextualReplApp(state_manager, show_setup)
    |
    v
on_mount()
    |-- Register themes (tunacode, nextstep, builtin)
    |-- Load saved theme from config
    |-- Initialize session metadata (project_id, working_dir, created_at)
    |
    v
if show_setup:
    push_screen(SetupScreen) → _on_setup_complete → _start_repl
else:
    _start_repl()
```

### REPL Request Flow

```
User types in Editor → Enter
    |
    v
on_editor_submit_requested()
    |
    v
handle_command() checks for /command or !shell
    |
    +-- /help, /model, /theme, etc. → execute command
    |
    +-- !cmd → ShellRunner.start()
    |
    +-- Agent request → request_queue.put(message)
    |
    v
_request_worker() coroutine
    |
    v
_process_request()
    |
    v
process_request(core.agents.main)
    |-- build_textual_tool_callback()
    |-- streaming_callback (throttled UI updates)
    |-- build_tool_result_callback()
    |-- build_tool_start_callback()
    |
    v
Streaming events:
    |-- message_update → _streaming_callback → streaming_output widget
    |-- tool_execution_start → status bar "running: tool_name"
    |-- tool_execution_end → ToolResultDisplay → ChatContainer.write()
    |-- turn_end → update iteration count
    |
    v
Finalized:
    |-- _get_latest_response_text()
    |-- render_agent_response() → ChatContainer.write()
    |-- _update_resource_bar()
    |-- await save_session()
```

### ESC Key Handling

```
User presses ESC
    |
    v
action_cancel_request()
    |
    v
EscHandler.handle_escape()
    |
    v
Priority 1: cancel current request task
    |
    v
Priority 2: cancel running shell command
    |
    v
Priority 3: clear editor input / paste buffer
```

### Rendering Pipeline

```
Agent/tool output → Renderer function
    |
    v
render_*(args, result, duration_ms, max_width)
    |
    v
Returns (content: RichRenderable, PanelMeta)
    |
    v
ChatContainer.write(content, panel_meta=meta)
    |
    v
CopyOnSelectStatic widget
    |-- Applies CSS classes from PanelMeta
    |-- Sets border_title/border_subtitle
    |-- Enables mouse selection copy
```

### Panel Rendering (NeXTSTEP Style)

```
RichPanelRenderer.render_tool()
    |
    v
Determine PanelType (TOOL, ERROR, SEARCH, INFO, SUCCESS, WARNING)
    |
    v
Lookup styles from PANEL_STYLES (border, title, subtitle colors)
    |
    v
Build content parts:
    |-- Arguments table (if any)
    |-- Result (truncated to MAX_PANEL_LINES)
    |-- Footer (duration_ms, line count)
    |
    v
Return (Group(*content), PanelMeta(css_class, border_title, border_subtitle))
```

## Why

The UI layer follows **NeXTSTEP User Interface Guidelines** (see `.claude/skills/neXTSTEP-ui/`): clear information hierarchy, no hidden state, consistent visual language, and respect for user attention.

**Why ChatContainer with insertion anchors?**
- Tool results may arrive after the agent response has already rendered.
- Insertion anchors ensure late-arriving content appears in the correct logical position.
- Without tracking, tool panels would always appear at the bottom, breaking conversation flow.

**Why ESC handler as separate component?**
- ESC has three distinct responsibilities (cancel request, cancel shell, clear input).
- Hardcoding logic in TextualReplApp creates tight coupling and makes testing difficult.
- Dependency injection via `EscHandler.handle_escape()` allows protocol-based testing.

**Why throttled streaming updates?**
- Textual re-rendering is expensive. Updating on every chunk causes UI lag.
- `STREAM_THROTTLE_MS = 100ms` batches updates while maintaining perceived responsiveness.

**Why mouse selection copy integration?**
- Terminal users expect text selection to copy without keyboard shortcuts.
- `SelectableRichVisual` injects offset metadata that Textual's selection requires but doesn't provide by default.
- `CopyOnSelectStatic.selection_updated()` debounces and copies on mouse release.

**Why separate renderers per tool?**
- Generic panels are functional but lack tool-specific formatting.
- `render_bash` shows exit code and working directory context.
- `render_read_file` applies syntax highlighting.
- `render_diagnostics` formats LSP errors with file positions.

**Why slash command system?**
- Extensible command registration via `COMMANDS` dict.
- Each command is an isolated `Command` subclass with clear `name`, `description`, `usage`.
- Easy to add new commands without modifying routing logic.

**Why status bar 3-zone layout?**
- Left: location context (branch, directory) — always relevant.
- Mid: edited files — operational state, shows what's been modified.
- Right: last/running action — immediate feedback on what just happened.
