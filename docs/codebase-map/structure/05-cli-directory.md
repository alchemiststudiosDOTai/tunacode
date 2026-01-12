---
title: CLI Module
path: tunacode/cli
type: directory
depth: 1
description: Command-line interface, REPL components, and slash commands
seams: [commands, repl_components, textual_repl]
---

# CLI Module (`src/tunacode/cli`)

## Where
`src/tunacode/cli/` - Command-line interface and REPL implementation.

## What
Implements the **command-line interface layer** for TunaCode:
- **REPL Engine**: Interactive read-eval-print loop components
- **Slash Commands**: User-invokable commands (`/help`, `/settings`, etc.)
- **Command Implementations**: Command execution logic
- **REPL Components**: Reusable REPL building blocks

## Directory Structure
```
cli/
├── commands/
│   ├── implementations/     # Command implementations
│   │   └── (command handlers)
│   └── slash/               # Slash command definitions
│       └── (slash command specs)
└── repl_components/         # REPL building blocks
    └── (reusable parts)
```

## How
The CLI module implements a **command-based interaction pattern**:

### Slash Commands System
Commands follow the `/command` pattern:
- **Command Discovery**: Commands registered in `commands/slash/`
- **Command Routing**: Routes user input to appropriate handler
- **Argument Parsing**: Typed argument extraction
- **Help System**: Auto-generated help from command definitions

**Command Categories**:
1. **Information**: `/help`, `/version`, `/status`
2. **Configuration**: `/settings`, `/model`, `/theme`
3. **Session**: `/clear`, `/reset`, `/save`
4. **Agent Control**: `/stop`, `/retry`, `/undo`
5. **Advanced**: `/debug`, `/profile`, `/export`

### REPL Components (`repl_components/`)
Modular REPL building blocks:
- **Input Handler**: Processes user input and routing
- **Output Formatter**: Formats agent responses for display
- **Command History**: Persistent command history
- **Auto-completion**: Context-aware suggestions
- **Syntax Highlighting**: Rich text formatting

**Component Design**:
- **Composability**: Components can be combined
- **Testability**: Each component tested in isolation
- **Extensibility**: New components integrate easily
- **State Management**: Components manage their own state

### Command Implementations (`commands/implementations/`)
Actual command execution logic:
```python
async def handle_settings_command(args: CommandArgs) -> CommandResult:
    """Handle /settings command."""
    # 1. Parse arguments
    # 2. Load current settings
    # 3. Apply changes
    # 4. Save configuration
    # 5. Return result
```

**Implementation Pattern**:
- **Async**: All commands are async for non-blocking execution
- **Validation**: Input validation before execution
- **Error Handling**: Clear error messages with recovery suggestions
- **Result Formatting**: Structured results for REPL display

## Why
**Separation of CLI Logic**: CLI concerns isolated from core business logic:
- **Testability**: Commands can be tested without UI dependencies
- **Reusability**: Components usable across different interfaces
- **Maintainability**: Command logic centralized and organized
- **Extensibility**: New commands added without refactoring

**User Experience**:
- **Discoverability**: `/help` lists all available commands
- **Consistency**: All commands follow same patterns
- **Feedback**: Clear success/error messages
- **History**: Command history enables replay and editing

**Design Principles**:
1. **Command Isolation**: Each command is self-contained
2. **Async First**: Non-blocking command execution
3. **Type Safety**: Command arguments are validated
4. **Error Recovery**: Commands suggest fixes on failure
5. **Documentation**: Auto-generated help from definitions

## Integration Points
- **UI**: `tunacode.ui` displays REPL and handles command input
- **Core**: Commands interact with `tunacode.core` for agent operations
- **Configuration**: Commands read/write `tunacode.configuration`
- **Tools**: Some commands directly invoke tools

## Code Quality Notes
- **Type Hints**: Command signatures fully typed
- **Validation**: Argument validation before execution
- **Error Messages**: Rich context and suggestions
- **Testing**: Commands tested with mock inputs
- **Documentation**: Docstrings generate help text

## Command Lifecycle
1. **Input**: User types `/command args`
2. **Routing**: CLI routes to appropriate handler
3. **Validation**: Arguments validated against schema
4. **Execution**: Command handler runs async
5. **Formatting**: Result formatted for display
6. **Output**: REPL displays result to user
