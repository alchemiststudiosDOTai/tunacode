---
title: UI Module
path: tunacode/ui
type: directory
depth: 1
description: Textual-based Terminal User Interface with NeXTSTEP-inspired design
seams: [app.py, main.py, renderers, screens, widgets]
---

# UI Module (`src/tunacode/ui`)

## Where
`src/tunacode/ui/` - User interface layer for the TunaCode TUI application.

## What
Implements the complete **Textual-based Terminal User Interface** for TunaCode, featuring:
- **TUI Application**: Main app loop and lifecycle management (`app.py`)
- **REPL Interface**: Read-eval-print loop for agent interaction (`main.py`)
- **Screens**: Modal dialogs and full-screen views (setup, model picker, etc.)
- **Widgets**: Custom Textual widgets for specialized rendering
- **Renderers**: Tool output formatting and display logic
- **Headless Mode**: Non-interactive execution path
- **Styling**: NeXTSTEP-inspired theme and CSS definitions

## Directory Structure
```
ui/
├── app.py                  # Main Textual application class
├── main.py                 # Entry point and REPL orchestration
├── logo_assets.py          # Pre-rendered ANSI logo loader
├── shell_runner.py         # TUI shell execution wrapper
├── repl_support.py         # REPL utilities and helpers
├── styles.py               # Style definitions and constants
├── commands/               # UI command handlers
│   └── (slash commands, REPL commands)
├── components/             # Reusable UI components
├── screens/                # Full-screen modal dialogs
│   ├── setup_screen.py
│   ├── model_picker.py
│   └── (other screens)
├── widgets/                # Custom Textual widgets
│   └── (specialized widgets)
├── renderers/              # Output formatting by tool type
│   └── tools/              # Tool-specific renderers
├── headless/               # Non-interactive execution
├── assets/                 # UI assets (pre-rendered ANSI art)
└── styles/                 # CSS and theme files
```

## How
The UI module follows a **layered component architecture**:

### Application Layer
- **`app.py`**: `TunaCodeApp` extends `textual.App`
  - Manages application lifecycle (startup, shutdown, screen switching)
  - Handles global state and event routing
  - Integrates with core agent system

### Presentation Layer
- **`screens/`**: Full-screen views for focused interactions
  - Setup wizard screens
  - Model picker with search/filter
  - Configuration dialogs
  - Session management views

### Component Layer
- **`widgets/`**: Reusable Textual widgets
  - Custom input widgets with validation
  - Specialized display widgets
  - Interactive controls

- **`components/`**: Composite UI patterns
  - Reusable widget combinations
  - Layout patterns
  - Interaction handlers

### Rendering Layer
- **`renderers/`**: Tool output formatting
  - `tools/` subdirectory contains renderer per tool type
  - Converts raw tool output to Rich/textual markup
  - Handles truncation, pagination, syntax highlighting

### Interaction Layer
- **`commands/`**: User command handlers
  - Slash command implementations
  - REPL command routing
  - Input parsing and validation

### Styling Layer
- **`styles.py`**: Programmatic style definitions
- **`styles/`**: CSS files for Textual styling
  - NeXTSTEP-inspired bevel and shadow effects
  - Color scheme definitions
  - Responsive layout rules

### Headless Layer
- **`headless/`**: Non-interactive execution path
  - Bypasses Textual app for CI/CD or scripting
  - Streams output to stdout/stderr
  - Simplified rendering for logs

## Why
**Separation of Concerns**: The UI module isolates all presentation logic from business logic:
- **Core Independence**: `tunacode.core` has no UI dependencies
- **Testability**: UI components can be tested in isolation
- **Flexibility**: Multiple frontends (TUI, headless, future GUI) can coexist
- **Theme Consistency**: Centralized styling ensures uniform appearance

**NeXTSTEP Design Philosophy**:
- **Uniformity**: Consistent interaction patterns across all screens
- **User Informed**: Real-time feedback for all agent actions
- **Clarity**: Clean, professional, retro-modern aesthetic
- **Object-Oriented**: Component-based architecture mirroring NeXTSTEP's design

**Design Principles**:
1. **Component Reusability**: Widgets and components are composable
2. **Lazy Loading**: Heavy UI components loaded on-demand
3. **Event-Driven**: Textual's event system for responsive updates
4. **Graceful Degradation**: Headless mode for environments without TTY

## Integration Points
- **Core Agent System**: `tunacode.core.agents` provides agent responses to display
- **Tool Execution**: `tunacode.tools` outputs are rendered by `renderers/tools/`
- **Configuration**: `tunacode.configuration` provides settings for UI initialization
- **Constants**: `tunacode.constants` provides UI_COLORS and theme definitions

## Code Quality Notes
- **Type Hints**: Full Textual type annotation for widget properties
- **CSS Organization**: Separate `.tcss` files for maintainable styling
- **Widget Testing**: Components designed for isolated unit testing
- **Performance**: Virtual scrolling for large outputs, lazy screen loading
