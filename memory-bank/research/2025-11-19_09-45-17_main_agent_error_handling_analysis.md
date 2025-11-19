# Research – Main Agent Error Handling Analysis

**Date:** 2025-11-19
**Owner:** claude
**Phase:** Research

## Goal
Analyze the current error handling patterns in the main agent system (`src/tunacode/core/agents/main.py` and related components) to identify gaps that cause CLI crashes and "blow-ups" as reported.

## Additional Search
- `grep -ri "error" .claude/`
- `grep -ri "exception" .claude/`
- `grep -ri "crash" .claude/`

## Findings

### Current Error Handling Architecture

The TunaCode agent system implements a multi-layered error handling strategy with several defensive mechanisms:

**File: `src/tunacode/core/agents/main.py`**
- **Lines 472-494**: RequestOrchestrator catches `UserAbortError`, `ToolBatchingJSONError`, and generic `Exception`
- **Issue**: All uncaught exceptions are re-raised without graceful handling
- **Pattern**: Logs error context, patches tool messages, but propagates exceptions upward

**File: `src/tunacode/cli/repl.py`**
- **Lines 164-248**: Main REPL error handling around `process_request()` calls
- **Caught**: `CancelledError`, `UserAbortError`, `UnexpectedModelBehavior`, generic `Exception`
- **Strength**: Attempts automatic recovery with `attempt_tool_recovery()`
- **Gap**: Silent failure in recursive UserAbortError handling (lines 232-234)

**File: `src/tunacode/cli/main.py`**
- **Lines 74-95**: Top-level CLI exception handling
- **Caught**: `KeyboardInterrupt`, `UserAbortError`, `ConfigurationError`, generic `Exception`
- **Issue**: Generic exception handler displays raw traceback to users (line 95)

### Error Recovery Mechanisms

**File: `src/tunacode/cli/repl_components/error_recovery.py`**
- **Lines 93-169**: Comprehensive `attempt_tool_recovery()` function
- **Lines 21-90**: Specialized `attempt_json_args_recovery()` for JSON parsing errors
- **Capability**: Recovers from malformed tool arguments and concatenated JSON objects
- **Strength**: Sophisticated parsing and recovery logic with detailed logging

### Critical Gaps That Cause CLI "Blow-ups"

#### 1. Async Task Management Vulnerabilities
**File: `src/tunacode/cli/main.py:64`**
```python
update_task = asyncio.create_task(asyncio.to_thread(check_for_updates))
```
- **Issue**: Background task created without error handling
- **Risk**: "Task was destroyed but it is pending" warnings and potential crashes
- **Impact**: Background exceptions can propagate to event loop

#### 2. MCP Server Cleanup Failures
**File: `src/tunacode/cli/main.py:102-107`**
```python
try:
    await cleanup_mcp_servers()
except Exception:
    pass  # Best effort cleanup
```
- **Issue**: Bare `except` clause silently ignores all cleanup failures
- **Risk**: Resource leaks, zombie processes, and inconsistent state
- **Impact**: System resource exhaustion and stability issues

#### 3. Agent Creation Error Propagation
**File: `src/tunacode/core/agents/agent_config.py:59-75`**
- **Issue**: File I/O errors during agent initialization not handled at CLI level
- **Risk**: Missing system prompts can crash application startup
- **Example**: `FileNotFoundError` during `load_system_prompt()` propagates up

#### 4. State Management Race Conditions
**File: `src/tunacode/cli/repl.py:279`**
```python
asyncio.create_task(warm_code_index())
```
- **Issue**: Concurrent tasks accessing shared state without synchronization
- **Risk**: Race conditions when multiple operations modify session state
- **Impact**: Data corruption and unpredictable behavior

#### 5. Inconsistent Exception Re-raising Patterns
**File: `src/tunacode/core/agents/main.py:472-494`**
```python
except UserAbortError:
    raise  # Re-raised without handling
except ToolBatchingJSONError:
    logger.error(...)
    raise  # Re-raised after logging
```
- **Issue**: Critical exceptions re-raised instead of handled gracefully
- **Risk**: Exceptions bypass CLI-level error handling
- **Impact**: Application crashes instead of user-friendly error messages

### Missing Error Handling Patterns

#### 1. Background Task Error Handling
- **Missing**: Error callbacks for async tasks created with `asyncio.create_task()`
- **Impact**: Unhandled task exceptions crash the event loop

#### 2. Resource Cleanup Validation
- **Missing**: Verification that MCP server cleanup actually succeeded
- **Impact**: Silent failures lead to resource leaks

#### 3. Agent Lifecycle Management
- **Missing**: Graceful degradation when agent initialization fails
- **Impact**: Application startup failures instead of fallback modes

#### 4. State Synchronization
- **Missing**: Session-level locking for concurrent state access
- **Impact**: Race conditions in multi-threaded async environments

### Error Propagation Flow

```
Tool Error → ToolExecutionError → Node Processor (handled, continues) →
RequestOrchestrator (logged, re-raised) → REPL (recovery attempt) → CLI (traceback display)
```

**Critical Gap**: The RequestOrchestrator re-raises exceptions instead of returning error states, breaking the defensive layers.

### Current Recovery Capabilities

1. **JSON Parsing Recovery**: Sophisticated recovery from malformed tool arguments
2. **Tool Execution Recovery**: Automatic retry and parsing from model text responses
3. **Configuration Error Handling**: User-friendly configuration error messages
4. **Cancellation Handling**: Graceful operation cancellation with cleanup

### Configuration Error Handling Patterns

**File: `src/tunacode/exceptions.py`**
- **Strength**: Comprehensive exception hierarchy with structured error messages
- **Examples**: `ConfigurationError` includes suggested fixes and recovery commands
- **Gap**: Not all error types use the structured error format consistently

## Key Patterns / Solutions Found

1. **Defensive Tool Execution**: Individual tool failures don't stop processing
2. **Sophisticated JSON Recovery**: Automatic recovery from model output parsing errors
3. **Contextual Error Logging**: Rich error context with request IDs and iteration tracking
4. **User-Guided Abort Flow**: UserAbortError includes feedback extraction and recursive processing
5. **Configuration Validation**: Detailed configuration error messages with actionable guidance

## Knowledge Gaps

1. **Agent Creation Error Boundaries**: Unclear where agent initialization errors should be caught
2. **Background Task Lifecycle**: Missing patterns for async task error handling and cleanup
3. **Resource Cleanup Guarantees**: No validation that critical cleanup operations succeed
4. **State Consistency**: Unknown impact of concurrent state modifications
5. **Error Recovery Limits**: Not clear which error types are recoverable vs. fatal

## References

### Key Files for Error Handling Implementation
- `src/tunacode/core/agents/main.py` - Main agent orchestration and error handling
- `src/tunacode/cli/repl.py` - Primary error handling boundary for user interactions
- `src/tunacode/cli/main.py` - Top-level CLI error handling and application lifecycle
- `src/tunacode/cli/repl_components/error_recovery.py` - Sophisticated error recovery mechanisms
- `src/tunacode/exceptions.py` - Comprehensive exception hierarchy definitions
- `src/tunacode/core/agents/agent_config.py` - Agent creation and configuration error handling

### Specific Line References for Critical Issues
- Async task vulnerability: `src/tunacode/cli/main.py:64`
- MCP cleanup issue: `src/tunacode/cli/main.py:102-107`
- Exception re-raising: `src/tunacode/core/agents/main.py:472-494`
- Recursive failure handling: `src/tunacode/cli/repl.py:232-234`
- Background task creation: `src/tunacode/cli/repl.py:279`

### Error Flow Boundaries
1. **CLI Layer** (`main.py:74-95`) - Final user-facing error boundary
2. **REPL Layer** (`repl.py:218-244`) - Primary error handling with recovery
3. **Agent Layer** (`main.py:472-494`) - Request-level error handling
4. **Tool Layer** (`node_processor.py:479-496`) - Individual tool error handling