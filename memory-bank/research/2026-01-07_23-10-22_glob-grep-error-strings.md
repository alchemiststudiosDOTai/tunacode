# Research – Glob/Grep Error String Pattern

**Date:** 2026-01-07
**Owner:** claude
**Phase:** Research
**Git Commit:** a891c71

## Goal

Document the inconsistent error handling in `glob` and `grep` tools that return error strings instead of raising `ModelRetry`, preventing LLM self-correction on recoverable errors like bad paths.

## Findings

### Problem Statement

Both `glob` and `grep` tools handle bad paths by returning error strings instead of raising exceptions:

| Behavior            | What happens                               | LLM self-correct? |
|---------------------|--------------------------------------------|-------------------|
| Raise ModelRetry    | Retry system kicks in                      | Yes               |
| Raise exception     | Wrapped as ToolExecutionError, agent halts | No                |
| Return error string | Tool "succeeds", LLM sees error in output  | No retry signal   |

### Affected Files

#### `src/tunacode/tools/glob.py` (lines 74-78)

```python
root_path = Path(directory).resolve()
if not root_path.exists():
    return f"Error: Directory '{directory}' does not exist"  # ← string, not exception
if not root_path.is_dir():
    return f"Error: '{directory}' is not a directory"
```

**Issue:** Directory validation returns error strings. LLM cannot self-correct.

#### `src/tunacode/tools/grep.py` (line 113)

```python
if not candidates:
    if return_format == "list":
        return []
    return f"No files found matching pattern: {include_pattern}"
```

**Issue:** No explicit directory validation. Returns "No files found" for non-existent directories. LLM cannot distinguish between "directory doesn't exist" and "no matches in valid directory."

### Reference Implementation (Correct Pattern)

#### `src/tunacode/tools/list_dir.py` (lines 182-186)

```python
if not dir_path.exists():
    raise ModelRetry(f"Directory not found: {dir_path}. Check the path.")

if not dir_path.is_dir():
    raise ModelRetry(f"Not a directory: {dir_path}. Provide a directory path.")
```

This was fixed per KB entry `list-dir-tool-execution-error.md`.

### Other Tools Using Correct Pattern

| Tool | File | Lines | Pattern |
|------|------|-------|---------|
| bash | `bash.py` | 163-167 | `raise ModelRetry(...)` for bad cwd |
| write_file | `write_file.py` | 21-25 | `raise ModelRetry(...)` if file exists |
| update_file | `update_file.py` | 24-28 | `raise ModelRetry(...)` if file doesn't exist |
| web_fetch | `web_fetch.py` | 82-109 | `raise ModelRetry(...)` for URL validation |
| @file_tool | `decorators.py` | 193-194 | Converts `FileNotFoundError` to `ModelRetry` |

### Error Flow Analysis

**ModelRetry Flow (Correct):**
```
LLM calls tool with bad path
  → Tool raises ModelRetry("Directory not found")
  → execute_with_retry catches ModelRetry
  → Matches NON_RETRYABLE_ERRORS → propagate
  → Agent sends error message to LLM
  → LLM self-corrects path and retries
  → Success
```

**Error String Flow (Broken):**
```
LLM calls glob with bad path
  → glob returns "Error: Directory does not exist"
  → execute_with_retry receives string result
  → No exception → returns "success" with error content
  → Agent sends error string to LLM as tool output
  → LLM cannot self-correct - no retry signal
```

### Retry Mechanism Details

From `src/tunacode/core/agents/agent_components/tool_executor.py`:

```python
NON_RETRYABLE_ERRORS = (
    UserAbortError,
    ModelRetry,           # ← Signals LLM to self-correct
    KeyboardInterrupt,
    SystemExit,
    ValidationError,
    ConfigurationError,
    ToolExecutionError,   # ← Terminal tool failure
    FileOperationError,
)
```

**Key insight:** `ModelRetry` is "non-retryable" by the infrastructure because it immediately propagates to the agent, which then sends the error to the LLM for self-correction. This is the **intended behavior** for recoverable user errors like bad paths.

### Test Coverage Gap

No existing tests for glob/grep path validation:
- `tests/test_tool_conformance.py` - Only discovery validation
- `tests/test_tool_retry.py` - Tests retry mechanism but not glob/grep specifically

**Missing tests:**
- `glob` with nonexistent directory → should raise `ModelRetry`
- `grep` with nonexistent path → should raise `ModelRetry`
- Both tools with helpful error messages for LLM context

## Key Patterns / Solutions Found

### Pattern: Exception-Based Error Signaling

**Current (Wrong):**
```python
if not root_path.exists():
    return f"Error: Directory '{directory}' does not exist"
```

**Fixed (Correct):**
```python
if not root_path.exists():
    raise ModelRetry(f"Directory not found: {directory}. Check the path.")
```

### Pattern: Why @file_tool Won't Work

From KB entry: `@file_tool` expects a required `filepath` positional arg, but both `glob` and `grep` have optional `directory="."`. Must use `@base_tool` with manual `ModelRetry` raises.

### Pattern: Informational vs Error Returns

- "No matches found" for valid directory with no results → OK as string (informational)
- "Directory does not exist" → Must be `ModelRetry` (recoverable error)

## Knowledge Gaps

1. **grep directory validation**: Need to verify where exactly grep validates (or doesn't validate) the directory path before `fast_glob`
2. **grep components**: `FileFilter.fast_glob()` may silently handle bad paths - need to trace through

## References

- `src/tunacode/tools/glob.py` - Glob tool implementation
- `src/tunacode/tools/grep.py` - Grep tool implementation
- `src/tunacode/tools/list_dir.py` - Reference implementation with correct pattern
- `src/tunacode/tools/decorators.py` - `@base_tool` and `@file_tool` decorators
- `src/tunacode/core/agents/agent_components/tool_executor.py` - Retry mechanism
- `.claude/debug_history/list-dir-tool-execution-error.md` - Previous fix for same pattern
- `tests/test_tool_retry.py` - Retry mechanism tests

## Proposed Fix

### For glob.py (lines 74-78)

```python
from pydantic_ai.exceptions import ModelRetry

# Replace:
if not root_path.exists():
    return f"Error: Directory '{directory}' does not exist"
if not root_path.is_dir():
    return f"Error: '{directory}' is not a directory"

# With:
if not root_path.exists():
    raise ModelRetry(f"Directory not found: {directory}. Check the path.")
if not root_path.is_dir():
    raise ModelRetry(f"Not a directory: {directory}. Provide a directory path.")
```

### For grep.py

Add explicit directory validation before `fast_glob`:

```python
from pydantic_ai.exceptions import ModelRetry

# Add after line 68:
dir_path = Path(directory).resolve()
if not dir_path.exists():
    raise ModelRetry(f"Directory not found: {directory}. Check the path.")
if not dir_path.is_dir():
    raise ModelRetry(f"Not a directory: {directory}. Provide a directory path.")
```

### Tests to Add

Create `tests/test_glob_grep_path_validation.py`:
- Test glob with nonexistent directory raises `ModelRetry`
- Test grep with nonexistent directory raises `ModelRetry`
- Test both with not-a-directory path raises `ModelRetry`
- Test error messages contain actionable context
