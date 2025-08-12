# TunaCode UI Architecture: First Principles

## Table of Contents
1. [UI Architecture Overview](#ui-architecture-overview)
2. [Core UI Flow](#core-ui-flow)
3. [Streaming and "Thinking" Mechanism](#streaming-and-thinking-mechanism)
4. [Key Files and Their Roles](#key-files-and-their-roles)
5. [State Management](#state-management)
6. [Visual Elements](#visual-elements)
7. [User Interaction Patterns](#user-interaction-patterns)

## UI Architecture Overview

TunaCode uses a **terminal-based UI** built on two primary libraries:

### Foundation Libraries

1. **prompt_toolkit** - Handles interactive terminal input
   - Multiline input with syntax highlighting
   - Custom keybindings (Ctrl+J for submit, Ctrl+D for exit)
   - Async-compatible input handling
   - Command history and autocompletion

2. **Rich** - Provides beautiful terminal output
   - Styled text with colors and formatting
   - Panel displays with rounded borders
   - Live updates for streaming content
   - Progress spinners and status indicators

### Architecture Pattern

The UI follows a **layered architecture**:

```
┌─────────────────────────────────────┐
│         REPL Layer (repl.py)        │  ← User interaction loop
├─────────────────────────────────────┤
│    UI Components (ui/ directory)     │  ← Display & input handling
├─────────────────────────────────────┤
│    Agent Core (agents/main.py)      │  ← Processing logic
├─────────────────────────────────────┤
│      State Manager (state.py)       │  ← Session & state tracking
└─────────────────────────────────────┘
```

### Key Design Decisions

- **Async-first**: All UI operations are async to prevent blocking
- **Decorator pattern**: Sync wrappers auto-generated for flexibility
- **Component separation**: UI logic separated from business logic
- **Progressive disclosure**: Streaming shows content as it arrives

## Core UI Flow

### REPL Lifecycle

The Read-Eval-Print Loop (`src/tunacode/cli/repl.py`) orchestrates the entire user interaction:

```python
# Simplified REPL flow
async def repl(state_manager: StateManager):
    while True:
        # 1. READ - Get user input
        user_input = await prompt_manager.get_input()

        # 2. EVAL - Process input
        if user_input.startswith('/'):
            result = await _handle_command(user_input, state_manager)
        else:
            result = await process_request(user_input, state_manager)

        # 3. PRINT - Display results
        await display_agent_output(result)

        # 4. LOOP - Continue
```

### Input Processing Pipeline

1. **User types input** → prompt_toolkit captures with multiline support
2. **Input validation** → Check for commands (/) vs agent requests
3. **Command routing**:
   - `/command` → CommandRegistry → specific command handler
   - Regular text → Agent processing pipeline
4. **Response display** → Rich panels or streaming updates

### Two Processing Modes

#### 1. Command Mode (slash commands)
```
User Input: /help
     ↓
CommandRegistry.execute()
     ↓
HelpCommand.execute()
     ↓
Display help panel
```

#### 2. Agent Mode (conversational)
```
User Input: "Explain this code"
     ↓
process_request() in repl.py
     ↓
agent.process_request() in main.py
     ↓
Streaming or batch response
```

## Streaming and "Thinking" Mechanism

### The "Thinking" State

When processing begins, TunaCode shows a spinner with the message defined in constants:

```python
UI_THINKING_MESSAGE = "[dim]Thinking...[/dim]"  # src/tunacode/constants.py
```

The spinner is managed in `src/tunacode/ui/output.py:112-133`:

```python
async def spinner(show: bool = True, spinner_obj=None, state_manager: StateManager = None):
    icon = SPINNER_TYPE  # "dots" spinner animation
    message = UI_THINKING_MESSAGE

    if not spinner_obj:
        spinner_obj = await run_in_terminal(
            lambda: console.status(message, spinner=icon)
        )
        if state_manager:
            state_manager.session.spinner = spinner_obj

    if show:
        spinner_obj.start()
    else:
        spinner_obj.stop()
```

### Token-Level Streaming

The agent supports real-time token streaming (`src/tunacode/core/agents/main.py:168-178`):

```python
# When streaming is enabled
if streaming_callback and STREAMING_AVAILABLE and Agent.is_model_request_node(node):
    async with node.stream(agent_run.ctx) as request_stream:
        async for event in request_stream:
            if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                # Stream individual token deltas
                if event.delta.content_delta and streaming_callback:
                    await streaming_callback(event.delta.content_delta)
```

### StreamingAgentPanel

The `StreamingAgentPanel` class (`src/tunacode/ui/panels.py:81-166`) provides progressive display:

```python
class StreamingAgentPanel:
    """Streaming agent panel using Rich.Live for progressive display."""

    def __init__(self, bottom: int = 1):
        self.content = ""
        self.live = None  # Rich.Live instance

    async def start(self):
        """Initialize Live display with thinking message"""
        self.live = Live(self._create_panel(), console=console, refresh_per_second=4)
        self.live.start()

    async def update(self, content_chunk: str):
        """Append new content and refresh display"""
        self.content = (self.content or "") + str(content_chunk)
        if self.live:
            self.live.update(self._create_panel())

    async def stop(self):
        """Clean shutdown to prevent extra lines"""
        if self.live:
            self.live.stop()
            console.print("", end="")  # Reset line
```

### Streaming Flow Diagram

```
1. User sends message
     ↓
2. Spinner shows "Thinking..."
     ↓
3. If streaming enabled:
   - Stop spinner
   - Create StreamingAgentPanel
   - Start Live display
     ↓
4. As tokens arrive:
   - streaming_callback() called
   - Panel.update() appends content
   - Rich.Live refreshes display
     ↓
5. On completion:
   - Panel.stop() cleans up
   - No duplicate output
```

## Key Files and Their Roles

### UI Layer Files

#### `src/tunacode/ui/output.py`
- **Purpose**: Core output functions and display utilities
- **Key functions**:
  - `print()` - Async wrapper around Rich console
  - `spinner()` - Manages thinking indicator
  - `banner()` - Displays ASCII art on startup
  - `get_context_window_display()` - Shows token usage

#### `src/tunacode/ui/panels.py`
- **Purpose**: Rich panel displays for structured content
- **Key components**:
  - `panel()` - Generic panel display with borders
  - `agent()` - Agent response panels
  - `StreamingAgentPanel` - Progressive content display
  - `help()` - Command help display
  - `tool_confirm()` - Tool execution confirmations

#### `src/tunacode/ui/console.py`
- **Purpose**: Console configuration and unified API
- **Features**:
  - Exports all display functions
  - Configures Rich console settings
  - Provides consistent styling

### REPL Layer Files

#### `src/tunacode/cli/repl.py`
- **Purpose**: Main REPL loop and request orchestration
- **Key functions**:
  - `repl()` - Main interaction loop
  - `process_request()` - Routes to agent with UI callbacks
  - `_handle_command()` - Processes slash commands

#### `src/tunacode/cli/repl_components/`
- **Modular components**:
  - `command_parser.py` - Parses command arguments
  - `tool_executor.py` - Handles tool execution with UI
  - `output_display.py` - Agent output formatting
  - `error_recovery.py` - Error handling and recovery (includes JSON concatenation recovery)

### Agent Layer Files

#### `src/tunacode/core/agents/main.py`
- **Purpose**: Agent orchestration with UI integration
- **UI-related features**:
  - Streaming callback support
  - Tool execution callbacks
  - Iteration progress tracking
  - Response state management

## State Management

### StateManager Structure

The `StateManager` maintains all UI-related state:

```python
class SessionState:
    # UI Components
    spinner: Optional[Status] = None
    streaming_panel: Optional[StreamingAgentPanel] = None

    # UI Preferences
    show_thoughts: bool = False
    enable_streaming: bool = True

    # Operation State
    is_streaming_active: bool = False
    operation_cancelled: bool = False

    # Tracking
    current_iteration: int = 0
    tool_calls: List[ToolCall] = []
    files_in_context: Set[str] = set()
```

### State Flow Example

```
1. User enables streaming
     ↓
state_manager.session.enable_streaming = True
     ↓
2. Request starts
     ↓
state_manager.session.spinner = await ui.spinner(True)
     ↓
3. Streaming begins
     ↓
state_manager.session.is_streaming_active = True
state_manager.session.streaming_panel = StreamingAgentPanel()
     ↓
4. Request completes
     ↓
state_manager.session.streaming_panel.stop()
state_manager.session.is_streaming_active = False
```

## Visual Elements

### Rich Library Usage

TunaCode leverages Rich's capabilities extensively:

1. **Console Configuration**
   ```python
   console = Console(force_terminal=True, legacy_windows=False)
   ```

2. **Panel Styling**
   ```python
   Panel(
       content,
       title=f"[bold]{title}[/bold]",
       border_style=colors.primary,
       box=ROUNDED,  # Rounded corners
       padding=(0, 1)
   )
   ```

3. **Color Scheme** (from `UI_COLORS`):
   - Primary: `#2563eb` (blue)
   - Success: `#10b981` (green)
   - Warning: `#f59e0b` (amber)
   - Error: `#ef4444` (red)
   - Muted: `#6b7280` (gray)

### ASCII Banner

The startup banner (`src/tunacode/ui/output.py:27-43`):

```
████████╗██╗   ██╗███╗   ██╗ █████╗
╚══██╔══╝██║   ██║████╗  ██║██╔══██╗
   ██║   ██║   ██║██╔██╗ ██║███████║
   ██║   ██║   ██║██║╚██╗██║██╔══██║
   ██║   ╚██████╔╝██║ ╚████║██║  ██║
   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝

 ██████╗ ██████╗ ██████╗ ███████╗  dev
██╔════╝██╔═══██╗██╔══██╗██╔════╝
██║     ██║   ██║██║  ██║█████╗
██║     ██║   ██║██║  ██║██╔══╝
╚██████╗╚██████╔╝██████╔╝███████╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝

● Caution: This tool can modify your codebase - always use git branches
```

## User Interaction Patterns

### Command vs Message Detection

```python
if user_input.startswith('/'):
    # Command mode - exact parsing required
    await _handle_command(user_input, state_manager)
else:
    # Agent mode - natural language processing
    await process_request(user_input, state_manager)
```

### Tool Confirmation Flow

When tools need confirmation:

1. **Tool requests confirmation** → `ToolUI.request_user_permission()`
2. **Display warning panel** → Shows what will be executed
3. **User responds** → y/n or multiline review
4. **Action taken** → Execute or skip based on response

### Progress Indicators

Multiple levels of progress feedback:

1. **Spinner** - "Thinking..." for initial processing
2. **Streaming text** - Real-time response generation
3. **Tool batches** - "Executing N tools in parallel"
4. **Iteration count** - "ITERATION: 3/15" in thought mode
5. **Token usage** - Context window percentage

### Error Handling Display

Errors are shown with context:

```python
try:
    # Operation
except ToolBatchingJSONError as e:
    await ui.error(f"Tool batching failed: {str(e)[:100]}...")
    # Patch orphaned tools
    patch_tool_messages(error_msg, state_manager)
```

### Input Patterns

1. **Single-line input** - Quick commands and queries
2. **Multiline input** - Complex prompts (Ctrl+J to submit)
3. **File references** - `@file.py` expands inline
4. **Command shortcuts** - `/c` → `/clear`
5. **Interrupt handling** - Ctrl+C cancels operations

## Summary

TunaCode's UI architecture achieves a balance between power and simplicity:

- **Terminal-native** but visually rich with styled output
- **Async throughout** for responsive interaction
- **Progressive disclosure** via streaming for immediate feedback
- **Clear separation** between UI, logic, and state layers
- **Extensible** command system for new functionality

The combination of prompt_toolkit for input and Rich for output creates a modern CLI experience that feels both familiar to terminal users and accessible to those expecting modern UI feedback patterns.
