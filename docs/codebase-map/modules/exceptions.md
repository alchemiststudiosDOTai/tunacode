---
title: Exceptions Module
path: src/tunacode/exceptions.py
type: file
depth: 0
description: Custom exception hierarchy for TunaCode
exports: [TunaCodeError, ToolExecutionError, ModelRetry, UserAbortError]
seams: [M]
---

# Exceptions Module

## Purpose
Defines a custom exception hierarchy for structured error handling throughout TunaCode.

## Exception Hierarchy

```
TunaCodeError (base)
├── ToolExecutionError
│   ├── FileOperationError
│   ├── CommandExecutionError
│   └── WebFetchError
├── ModelRetry
├── UserAbortError
├── ConfigurationError
├── StateError
├── AuthorizationError
└── GlobalRequestTimeoutError
```

## Exception Classes

### TunaCodeError
Base exception for all TunaCode errors:
- Provides consistent error type
- Allows catching all TunaCode errors
- Includes error context

### ToolExecutionError
Raised when tool execution fails:
- **bash** - Command failed or timed out
- **glob** - Pattern matching error
- **grep** - Search execution error
- **read_file** - File read failure
- **write_file** - File write failure
- **update_file** - File update failure
- **web_fetch** - HTTP request failure

**Attributes:**
- `tool_name` - Name of the tool
- `message` - Error description
- `original_error` - Underlying exception

### FileOperationError
Specialized for file system operations:
- FileNotFoundError handling
- PermissionError handling
- UnicodeDecodeError handling
- OSError handling

### ModelRetry
Signals the model should retry:
- Used for recoverable errors
- Triggers agent retry logic
- Provides retry guidance

**Common Causes:**
- Invalid file path
- Missing required arguments
- Temporary failures
- Retryable errors

### UserAbortError
Raised when user cancels operation:
- Ctrl+C during tool execution
- Confirmation rejection
- Session termination

### ConfigurationError
Configuration-related errors:
- Invalid config format
- Missing required settings
- Model not found
- Invalid template

### StateError
State management errors:
- Session load failure
- State corruption
- Invalid state transition

### AuthorizationError
Authorization failures:
- Tool authorization denied
- Permission errors
- Policy violations

### GlobalRequestTimeoutError
Request timeout:
- Overall request exceeded timeout (excluding user interaction time)
- Agent iteration limit
- Unproductive limit reached

**Note:** Time spent waiting for user input (tool confirmations, plan approvals)
does NOT count toward the global timeout. The timeout clock pauses during
user interaction and resumes when the agent continues processing. See
`TimeoutPauseState` and `wait_for_with_pause()` in `core/agents/main.py`.

## Error Handling Strategy

**Tools Layer:**
```python
@base_tool
async def tool_func(...):
    try:
        # Tool logic
        pass
    except Exception as e:
        raise ToolExecutionError("tool_name", str(e))
```

**Agent Layer:**
```python
try:
    result = await tool_func(...)
except ToolExecutionError:
    # Log and continue
    pass
except ModelRetry:
    # Trigger retry
    pass
```

**UI Layer:**
```python
try:
    await process_request(...)
except UserAbortError:
    # Clean exit
    pass
except TunaCodeError as e:
    # Display error to user
    render_error(e)
```

## Error Messages

Exceptions that include guidance are formatted via a shared formatter in
`src/tunacode/exceptions.py` to keep output consistent and DRY. The formatter
builds a base message and appends optional sections in a fixed order.

**Section order:**
- Suggested fix
- More help
- Valid examples
- Recovery commands
- Troubleshooting steps

**Example output:**
```
Validation failed: Bad input

Suggested fix:
Use a valid value

Valid examples:
  - tunacode --help
  - tunacode --setup
```

## Integration Points

- **tools/decorators.py** - Error wrapping in decorators
- **core/agents/** - Error handling in agent loop
- **ui/renderers/errors.py** - Error display rendering
- **All modules** - Raise TunaCodeError exceptions

## Seams (M)

**Modification Points:**
- Add new exception types
- Extend error attributes
- Customize error messages
- Add error recovery strategies

**Best Practices:**
- Always wrap low-level exceptions
- Provide clear error messages
- Include context and suggestions
- Use appropriate exception type
- Never silently swallow errors
