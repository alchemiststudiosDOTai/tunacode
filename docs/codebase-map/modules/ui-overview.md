---
title: UI Module
path: src/tunacode/ui
type: directory
depth: 1
description: Textual-based TUI interface for TunaCode REPL
exports: [TextualReplApp, RichPanelRenderer, Screen classes]
seams: [M, D]
---

# UI Module

## Purpose
Implements the terminal user interface using the Textual framework, following NeXTSTEP design principles for uniformity and user feedback.

## Key Components

### Main Application (app.py)

**TextualReplApp Class**
- Inherits from `textual.app.App`
- Main REPL application entry point
- Manages UI composition and event handling

**Key Methods:**
- **compose()** - Declarative UI layout definition
- **on_mount()** - Initialization (themes, config, workers)
- **watch_theme()** - Dynamic theme switching
- **streaming_callback()** - Real-time response streaming
- **on_tool_result_display()** - Tool output rendering

**Layout Components:**
- ResourceBar - Token usage and session info
- RichLog - Main conversation display
- Editor - Multi-line input widget
- StatusBar - Current mode and status
- LoadingIndicator - Async operation feedback

### Welcome Banner (welcome.py)

**generate_logo / show_welcome**
- Loads the pre-rendered ANSI logo from `ui/assets/logo.ansi`
- Renders the logo and onboarding commands in the RichLog

#### Logo Assets (logo_assets.py)

- Centralized loader for pre-rendered ANSI logos used by the UI

### Screen Management (screens/)

Modal screens for specific workflows:
- **ModelPickerScreen** - Model selection interface
- **SessionPickerScreen** - Session load/save interface
- **SetupScreen** - Initial configuration wizard
- **ThemePickerScreen** - Theme selection
- **UpdateConfirmScreen** - Tool change confirmation

Each screen uses `app.push_screen()` / `app.dismiss()` pattern.

### Renderer System (renderers/)

Specialized renderers for tool outputs:

#### panels.py
**RichPanelRenderer Class**
- Generic panel rendering with NeXTSTEP-style zones
- Standardized 4-zone layout:
  1. Header - Tool name and status
  2. Selection Context - Parameters/filters
  3. Primary Viewport - Main content
  4. Status/Metrics - Duration, counts, truncation notices

Tool panels render Zone 2 with a hook-arrow prefix for the primary parameters.
File-based tools show the path relative to the current working directory.

#### tools/
Specialized renderers for each tool:
- **bash.py** - Command output with exit codes
- **glob.py** - File listing with counts
- **grep.py** - Search results with context
- **read_file.py** - File content with line numbers
- **update_file.py** - Diff visualization
- **list_dir.py** - Directory tree view
- **web_fetch.py** - Web content summary
- **research.py** - Research agent results
- **diagnostics.py** - LSP error display

Tool renderers clamp content widths against the viewport and account for prefixes
and line-number gutters so panels stay within narrow terminal widths.

**Width management details:**
- `TextualReplApp.on_tool_result_display()` computes an available content width
  from the RichLog/viewport and subtracts a fixed horizontal inset so text
  wraps safely inside the panel frame.
- **panel_widths.py** - Centralized width calculation module (PR #244). Contains
  `tool_panel_frame_width(max_line_width)` which returns the explicit panel frame
  width (`max_line_width + TOOL_PANEL_HORIZONTAL_INSET`). This replaces the
  previous pattern of using `expand=True` indirection with explicit, verifiable
  widths (Gate 5 compliance).
- Tool renderers receive `max_line_width` as a parameter and use it for content
  truncation. The frame width is computed by `tool_panel_frame_width()`.
- Tool renderers reserve space for prefixes (indentation, grep line-number
  gutters, bullets) before truncating content, so the full rendered line stays
  within the computed width.
- Syntax-highlighted panels (`read_file`, `write_file`) pass an explicit
  `code_width` to Rich `Syntax` to account for line-number gutters and avoid
  overflow in small terminals.

### Widgets (widgets/)

Custom Textual widgets:
- **Editor** - Multi-line input with paste buffering
- **ResourceBar** - Token and cost tracking
- **StatusBar** - Mode and session status
- **Messages** - Rich message display
- **FileAutocomplete** - File path completion
- **CommandAutocomplete** - Command completion

### Commands (commands/)

REPL command implementations:
- **HelpCommand** - `/help` - Show available commands
- **ClearCommand** - `/clear` - Clear agent working state (UI, thoughts, todos) - messages preserved for /resume
- **YoloCommand** - `/yolo` - Toggle auto-confirm for tool executions
- **DebugCommand** - `/debug` - Toggle debug logging to screen (logs to ~/.local/share/tunacode/logs/)
- **ModelCommand** - `/model` - Reload config, then open model picker or switch directly (invalidates agent cache)
- **BranchCommand** - `/branch` - Create conversation branch
- **PlanCommand** - `/plan` - Toggle plan mode
- **ThemeCommand** - `/theme` - Switch UI theme
- **ResumeCommand** - `/resume` - Resume previous session
- **UpdateCommand** - `/update` - Check for and install updates

### Supporting Components

#### repl_support.py
Helper functions and callbacks:
- **format_user_message()** - Message formatting
- **build_tool_result_callback()** - Tool result handling
- **build_tool_progress_callback()** - Progress updates
- **build_textual_tool_callback()** - Tool execution

#### shell_runner.py
**ShellRunner Class**
- Executes shell commands (prefixed with `!`)
- Async subprocess management
- Stdout/stderr capture and display
- Timeout and cancellation handling

#### styles.py
CSS styling definitions for TUI components.

### Headless Mode (headless/)

Non-interactive output for scripting and CI:
- **output.py** - Plain text output rendering

## Interaction Flows

### User Input Flow
```
Editor → EditorSubmitRequested → handle_command
  → /command → Command.execute()
  → !shell → ShellRunner.execute()
  → text → request_queue → process_request()
```

### AI Response Flow
```
process_request() → streaming_callback() → streaming_output widget
  → Tool calls → execute_tools_parallel()
  → Tool results → on_tool_result_display() → tool_panel_smart() → RichLog
```

### Tool Confirmation Flow
```
Tool call → request_tool_confirmation() → _show_inline_confirmation()
  → User input (1/2/3) → on_key() → Authorization decision → Tool execution
```

## NeXTSTEP Design Principles

1. **Uniformity** - Consistent panel layouts and styling
2. **User Informed** - Real-time feedback on all operations
3. **Professional Aesthetic** - Clean, retro-modern look
4. **Clear Information Hierarchy** - Zoned layouts with headers

## Integration Points

- **core/agents/** - Request processing via process_request()
- **core/state/** - StateManager for UI updates
- **tools/** - Tool execution and authorization
- **renderers/** - Specialized output formatting

## Seams (M, D)

**Modification Points:**
- Add new screens for additional workflows
- Create custom widgets for specialized input
- Extend renderer system for new tool types
- Customize CSS styling for themes

**Extension Points:**
- Implement new REPL commands
- Add specialized screen types
- Create custom renderer strategies
- Extend widget functionality
