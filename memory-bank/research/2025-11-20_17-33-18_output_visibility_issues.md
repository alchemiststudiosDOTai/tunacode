# Research – Output Visibility Issues in TunaCode CLI

**Date:** 2025-11-20
**Owner:** Claude Code Agent
**Phase:** Research
**Git Commit:** 3e3c759f27071c7bd8187e273c23e0897142af86

## Goal
Summarize all existing knowledge about output visibility issues where users or agents cannot see the results of basic actions in the TunaCode CLI.

## Additional Search
- `grep -ri "output.*visibl" .claude/` - No direct matches found in knowledge base
- `grep -ri "can't see\|cannot see\|not visible" .claude/` - No direct matches found

## Findings
### Relevant files & why they matter:

#### Core Output Handling Files
- `src/tunacode/cli/main.py:55-143` - Main CLI entry point with async background task creation
- `src/tunacode/cli/repl.py:300-461` - Main REPL loop handling user input and output coordination
- `src/tunacode/ui/console.py` - Console access and error/warning/debug logging functions
- `src/tunacode/ui/output.py:70` - `run_in_terminal()` function that handles all output
- `src/tunacode/ui/panels.py:131-416` - `StreamingAgentPanel` class for real-time display

#### Critical Implementation Files
- `src/tunacode/core/agents/agent_components/streaming.py:265-278` - **CRITICAL BUG**: Missing `node._did_stream = False` reset in exception handler
- `src/tunacode/core/agents/main.py:186` - First-chunk character loss due to empty content delta filtering
- `src/tunacode/cli/repl_components/output_display.py:13-44` - Agent output display logic with streaming support
- `src/tunacode/core/agents/agent_components/response_state.py` - Response state management with state machine

#### Configuration and Settings
- `src/tunacode/configuration/defaults.py:28` - `enable_streaming: True` setting
- `src/tunacode/configuration/models.py` - User configuration models affecting output

## Key Patterns / Solutions Found

### 1. Critical Streaming State Corruption Bug (HIGH PRIORITY)
**Location**: `src/tunacode/core/agents/agent_components/streaming.py:265-278`
**Issue**: When streaming fails mid-stream, the exception handler doesn't reset `node._did_stream = False`, causing "You must finish streaming before calling run()" errors
**Impact**: Users cannot see output after streaming failures
**Known Fix**: Add `node._did_stream = False` reset in exception handler (documented but not implemented)

### 2. First-Chunk Character Loss (MEDIUM PRIORITY)
**Location**: `src/tunacode/core/agents/main.py:186` and `src/tunacode/ui/panels.py:190-203`
**Issue**: Aggressive content filtering causes first characters to disappear from messages
**Impact**: Messages like "TUNACODE DONE:" appear as "UNACODE DONE:"
**Pattern**: Empty content delta filtering is too aggressive

### 3. Async Task Coordination Issues (MEDIUM PRIORITY)
**Location**: `src/tunacode/cli/repl.py:412-415`
**Issue**: Background tasks for user requests may not be properly awaited before returning control
**Impact**: Output may appear delayed or after user gets new prompt
**Pattern**: Background task creation without proper completion awaiting

### 4. Race Conditions in UI Updates (LOW PRIORITY)
**Location**: `src/tunacode/ui/panels.py:294-323`
**Issue**: Shared state modification between `update()` and `_animate_dots()` without synchronization
**Impact**: Concurrent updates can cause state inconsistency and missed content
**Pattern**: Non-atomic UI state updates

### 5. Tool Output Buffering Delay (LOW PRIORITY)
**Location**: `src/tunacode/cli/main.py:531-562`
**Issue**: Buffered tool execution may complete after user sees prompt
**Impact**: Tool results appear delayed, making it seem like action had no effect
**Pattern**: Batch execution with timing issues

## Architecture Overview

### Output Flow System
1. **User Input** → `multiline_input()` → command parsing
2. **Command Processing** → either:
   - Shell command execution (immediate output)
   - Agent request processing (async background task)
3. **Agent Request** → background task creation → `execute_repl_request()`
4. **Streaming Setup** → `StreamingAgentPanel.start()` → agent processing
5. **Token Streaming** → `streaming_callback()` → panel updates
6. **Tool Execution** → buffering → parallel execution → results
7. **Completion** → panel cleanup → context display → return to prompt

### Key Patterns Identified
- **Streaming Architecture**: Uses Rich.Live panels for real-time content updates at 4Hz refresh rate
- **Lazy Console Initialization**: Defers console creation to optimize startup
- **Background Task Pattern**: All user requests run in background tasks with error callbacks
- **Tool Buffering**: Read-only tools batched for performance, writes executed immediately
- **Streaming Fallback**: Streaming degrades gracefully to non-streaming on errors

## Knowledge Gaps
- **Test Coverage**: No tests for streaming failure recovery or output visibility issues
- **Performance Metrics**: No measurements of output latency or timing issues
- **User Experience Data**: No documented user reports or feedback about output visibility
- **Error Recovery Effectiveness**: Limited data on how often error recovery masks important output
- **Configuration Impact**: Unclear how different configuration options affect output visibility

## Existing Mitigations
- `enable_streaming` configuration option (default: true)
- `fallback_verbosity` setting with options: minimal, normal, detailed
- `show_thoughts` setting controls debug visibility
- Comprehensive debug state tracking in session manager
- Multiple layers of error handling and recovery mechanisms

## References
### GitHub Permalinks
- Main CLI entry point: https://github.com/alchemiststudiosDOTai/tunacode/blob/3e3c759f27071c7bd8187e273c23e0897142af86/src/tunacode/cli/main.py
- REPL loop: https://github.com/alchemiststudiosDOTai/tunacode/blob/3e3c759f27071c7bd8187e273c23e0897142af86/src/tunacode/cli/repl.py
- Streaming agent panel: https://github.com/alchemiststudiosDOTai/tunacode/blob/3e3c759f27071c7bd8187e273c23e0897142af86/src/tunacode/ui/panels.py
- Streaming component: https://github.com/alchemiststudiosDOTai/tunacode/blob/3e3c759f27071c7bd8187e273c23e0897142af86/src/tunacode/core/agents/agent_components/streaming.py

### File Paths for Review
- `src/tunacode/cli/main.py` - CLI entry point and background task management
- `src/tunacode/cli/repl.py` - Main REPL loop and user interaction
- `src/tunacode/ui/panels.py` - Streaming panel implementation
- `src/tunacode/core/agents/agent_components/streaming.py` - Core streaming functionality
- `src/tunacode/cli/repl_components/output_display.py` - Output display logic
- `src/tunacode/configuration/defaults.py` - Default configuration settings

### Next Steps for Investigation
1. Implement the critical streaming state reset fix in `streaming.py:265-278`
2. Review and fix content filtering in `main.py:186` and `panels.py:190-203`
3. Add proper task completion awaiting in `repl.py:412-415`
4. Create comprehensive tests for streaming failure scenarios
5. Add user-facing indicators for background task completion status
