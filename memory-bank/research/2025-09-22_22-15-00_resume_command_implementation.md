# Research – Lightweight /resume Command Implementation
**Date:** 2025-09-22 22:15:00
**Owner:** context-engineer:research
**Phase:** Research

## Goal
Summarize all *existing knowledge* before any new work.

- Additional Search:
  - `grep -ri "resume" .claude/`

## Findings
- Relevant files & why they matter:
  - `src/tunacode/cli/commands/base.py` → Command base classes and SimpleCommand pattern
  - `src/tunacode/cli/commands/registry.py` → Command registration and discovery system
  - `src/tunacode/cli/commands/implementations/conversation.py` → Existing conversation management commands
  - `src/tunacode/core/state.py` → SessionState dataclass with 37 fields for tracking conversation state
  - `src/tunacode/utils/user_configuration.py` → JSON persistence patterns for config files
  - `src/tunacode/utils/system.py` → Session directory patterns (`~/.tunacode/sessions/{session_id}`)
  - `tests/characterization/state/test_session_management.py` → Session management characterization showing no existing disk persistence

## Key Patterns / Solutions Found

### 1. Command Implementation Pattern
- **Location**: `src/tunacode/cli/commands/implementations/[name].py`
- **Base Class**: `SimpleCommand` with `CommandSpec`
- **Registration**: Add to `command_classes` list in `registry.py` line ~140
- **Minimal Code**: ~20 lines for basic command
- **Example**: `YoloCommand`, `ClearCommand` - simple state toggle commands

### 2. Session Persistence Patterns
- **Config Storage**: JSON files in `~/.config/tunacode/config.json`
- **Session Directory**: `~/.tunacode/sessions/{session_id}/` pattern already exists
- **JSON Serialization**: Standard pattern with error handling in `user_configuration.py`
- **Directory Creation**: `mkdir(mode=0o700, parents=True, exist_ok=True)` pattern

### 3. Essential Session Data for Resume
- **Must Preserve**: `messages`, `user_config`, `current_model`, `session_id`, `total_cost`, `files_in_context`, `session_total_usage`
- **Can Reset**: Runtime state (spinners, panels), temporary flags, agent instances, iteration counters
- **Message Format**: Dict-based with `role`/`content` or complex pydantic-ai objects

### 4. Lightweight Implementation Strategy
- **File Location**: `~/.tunacode/sessions/{session_id}/session_state.json`
- **Data Structure**: Subset of SessionState (8-10 essential fields)
- **Save Strategy**: Manual save command + auto-save on exit
- **Load Strategy**: List available sessions + load by session_id
- **Dependencies**: No new dependencies required - uses existing JSON and file patterns

## Knowledge Gaps
- Message serialization format for complex pydantic-ai message objects
- Whether to implement auto-save or manual-save-only
- Session listing and management UI patterns
- Error handling for corrupted session files
- Performance impact of saving large message histories

## Implementation Plan
1. Create `ResumeCommand` class following SimpleCommand pattern
2. Implement session save/load functions using existing JSON patterns
3. Add session listing functionality
4. Integrate with existing session directory structure
5. Add error handling and validation

## References
- `src/tunacode/cli/commands/implementations/debug.py` - SimpleCommand examples
- `src/tunacode/utils/user_configuration.py:61-82` - JSON save/load patterns
- `src/tunacode/core/state.py:34-101` - SessionState dataclass structure
- `src/tunacode/cli/commands/registry.py:140-167` - Command registration pattern
- `src/tunacode/utils/system.py:61-73` - Session directory patterns
