# Research – bash-activation-implementation
**Date:** 2025-09-30
**Owner:** context-engineer
**Phase:** Research
**Git Commit:** 478538de9237135393d1877afe517b1bba330a11
**Git Branch:** codex-fork

## Goal
Research the codebase to understand how to implement `!` bash activation in the CLI, allowing users to type `!` to activate bash tools and run commands directly within the interactive CLI interface.

## Findings

### Relevant files & why they matter:

#### CLI Architecture and Input Handling
- `/home/fabian/tunacode/tunacode-rs/tui/src/bottom_pane/chat_composer.rs` → Main input handling and command parsing logic; where `!` detection would need to be implemented
- `/home/fabian/tunacode/tunacode-rs/tui/src/slash_command.rs` → Existing slash command system; can be extended to support `!` as a special prefix
- `/home/fabian/tunacode/tunacode-rs/tui/src/bottom_pane/command_popup.rs` → Command popup implementation; pattern to follow for bash command popup
- `/home/fabian/tunacode/tunacode-rs/tui/src/chatwidget.rs` → Command dispatch system; where bash commands would be routed

#### Bash Integration and Execution
- `/home/fabian/tunacode/tunacode-rs/core/src/bash.rs` → Tree-sitter based bash parsing with security validation; robust parsing infrastructure already exists
- `/home/fabian/tunacode/tunacode-rs/core/src/shell.rs` → Cross-platform shell detection and command formatting; handles bash `-lc` invocation patterns
- `/home/fabian/tunacode/tunacode-rs/core/src/spawn.rs` → Process spawning and async execution; infrastructure for running bash commands
- `/home/fabian/tunacode/tunacode-rs/core/src/exec.rs` → Main command execution entry point; where bash commands would be processed
- `/home/fabian/tunacode/tunacode-rs/core/src/parse_command.rs` → Command parsing and categorization; can be leveraged for bash command analysis

#### Protocol and Tool Integration
- `/home/fabian/tunacode/tunacode-rs/protocol/src/lib.rs` → Protocol definitions including LocalShellCall; existing shell tool infrastructure
- `/home/fabian/tunacode/tunacode-rs/core/src/openai_tools.rs` → OpenAI tool integration; how tools are integrated into the system

## Key Patterns / Solutions Found

### Existing Tool Activation Patterns
- **Slash Commands**: `/` prefix triggers command popup with fuzzy matching (tui/src/slash_command.rs:12-30)
- **File References**: `@` prefix triggers file search popup for path completion
- **Command Dispatch**: Commands routed through `dispatch_command()` method in chatwidget.rs
- **Popup State Machine**: Single active popup system with clear state transitions

### Bash Integration Infrastructure
- **Tree-sitter Parsing**: Robust bash parsing with security validation in core/src/bash.rs
- **Safe Command Execution**: `try_parse_word_only_commands_sequence()` for safe command validation
- **Process Management**: Async process spawning with proper cleanup and timeout handling
- **Cross-platform Support**: Shell detection and platform-specific command formatting

### Command Processing Flow
1. **Input Detection**: Special characters (`/`, `@`) detected in chat_composer.rs
2. **Popup Activation**: Appropriate popup appears with filtering capabilities
3. **Command Selection**: User selects command/file → content inserted or dispatched
4. **Execution**: Commands routed through dispatch system to appropriate handlers

### Security and Safety Features
- **Command Validation**: Tree-sitter based parsing prevents dangerous constructs
- **Sandbox Integration**: Multiple sandbox modes (None, MacosSeatbelt, LinuxSeccomp)
- **Timeout Handling**: Process termination and output truncation
- **Permission Management**: Approval policies and permission escalation handling

## Knowledge Gaps

### Implementation-specific Questions
- **UI Integration**: How to visually distinguish bash mode from regular input
- **Command History**: Whether bash commands should be integrated into chat history
- **Completion System**: What level of bash command completion should be provided
- **Error Handling**: How bash command errors should be displayed and handled

### Integration Points
- **Command Routing**: Exact integration point with existing slash command system
- **Protocol Extension**: Whether to extend LocalShellCall or create new bash-specific protocol
- **State Management**: How bash mode interacts with existing popup state machine

## Implementation Requirements

### Core Changes Needed
1. **Input Processing Extension**: Modify `chat_composer.rs` to detect `!` prefix and trigger bash mode
2. **Command System Extension**: Extend slash command system or create separate bash command handling
3. **UI Components**: Add bash command popup with appropriate styling and behavior
4. **Integration Points**: Connect with existing bash parsing and execution infrastructure

### Safety Considerations
- Leverage existing tree-sitter bash parsing for command validation
- Integrate with existing sandbox and permission systems
- Use existing timeout and process management infrastructure
- Maintain consistency with current security model

## References

### Primary Implementation Files
- `tui/src/bottom_pane/chat_composer.rs` - Input handling and special character detection
- `tui/src/slash_command.rs` - Slash command system to extend
- `core/src/bash.rs` - Bash parsing and validation
- `core/src/exec.rs` - Command execution infrastructure
- `core/src/shell.rs` - Shell detection and formatting

### Supporting Infrastructure
- `tui/src/bottom_pane/command_popup.rs` - Popup implementation patterns
- `tui/src/chatwidget.rs` - Command dispatch system
- `protocol/src/lib.rs` - Protocol definitions and shell tool integration
- `core/src/parse_command.rs` - Command parsing and categorization

### Additional Research
- `grep -ri "bash\|shell\|command" tunacode-rs/ --include="*.rs"` - For comprehensive bash-related code
- Existing LocalShellCall implementation for tool integration patterns