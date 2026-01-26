# Tools Architecture

Tools are async functions that the AI agent calls to interact with the system. This document explains how they work.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Tool Function                          │
│                  async def bash(command)                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    @base_tool / @file_tool                  │
│  - Logs invocations                                         │
│  - Routes exceptions                                        │
│  - Loads XML prompts into __doc__                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Exception Hierarchy                      │
│  ModelRetry → AI tries again                                │
│  ToolExecutionError → Tool failed                           │
│  FileOperationError → File operation failed                 │
└─────────────────────────────────────────────────────────────┘
```

## Decorators

### `@base_tool`

Wraps any async tool function with:

1. **Logging** - Logs every call with arguments
2. **Error handling** - Routes exceptions appropriately
3. **XML prompt loading** - Injects documentation from XML files

```python
from tunacode.tools.decorators import base_tool

@base_tool
async def my_tool(arg: str) -> str:
    """Tool docstring (may be replaced by XML prompt)."""
    return f"result: {arg}"
```

**Exception routing:**

| Exception | Action |
|-----------|--------|
| `ModelRetry` | Pass through (AI retries) |
| `ToolExecutionError` | Pass through (already formatted) |
| `FileOperationError` | Pass through (already formatted) |
| Any other exception | Wrap in `ToolExecutionError` |

### `@file_tool`

Extends `@base_tool` for file operations. First parameter must be `filepath: str`.

```python
from tunacode.tools.decorators import file_tool

@file_tool
async def read_something(filepath: str) -> str:
    """Read a file."""
    with open(filepath) as f:
        return f.read()
```

**File-specific error handling:**

| Exception | Converts to | Why |
|-----------|-------------|-----|
| `FileNotFoundError` | `ModelRetry` | AI can correct the path |
| `PermissionError` | `FileOperationError` | Access denied |
| `UnicodeDecodeError` | `FileOperationError` | Encoding issue |
| `IOError` / `OSError` | `FileOperationError` | I/O failure |

## Exceptions

All exceptions live in `tunacode/exceptions.py`.

### `ModelRetry`

From `pydantic_ai.exceptions`. Tells the AI to try the tool again with different arguments.

```python
from pydantic_ai.exceptions import ModelRetry

raise ModelRetry("File not found: /wrong/path. Check the path.")
```

### `ToolExecutionError`

Tool failed in a way the AI should know about.

```python
from tunacode.exceptions import ToolExecutionError

raise ToolExecutionError(
    tool_name="my_tool",
    message="Something went wrong",
    original_error=e,           # Optional
    suggested_fix="Try X",      # Optional
    recovery_commands=["cmd1"]  # Optional
)
```

### `FileOperationError`

File operation failed.

```python
from tunacode.exceptions import FileOperationError

raise FileOperationError(
    operation="read",           # "read", "write", "access", "decode"
    path="/path/to/file",
    message="Permission denied",
    original_error=e            # Optional
)
```

## XML Prompts

Tool documentation lives in `tunacode/tools/prompts/{tool_name}_prompt.xml`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<tool_prompt>
    <description>
        Full documentation the AI sees when deciding to use this tool.
        Explain what it does, when to use it, examples.
    </description>

    <parameters>
        <parameter name="pattern" required="true">
            <description>The search pattern</description>
            <type>string</type>
        </parameter>
        <parameter name="mode" required="false">
            <description>Output mode</description>
            <type>string</type>
            <enum>content</enum>
            <enum>files_only</enum>
        </parameter>
    </parameters>
</tool_prompt>
```

The `@base_tool` decorator loads this and sets `tool.__doc__` to the description text.

## Tool Registry

| Tool | Decorator | First Param | Purpose |
|------|-----------|-------------|---------|
| `bash` | `@base_tool` | `command: str` | Run shell commands |
| `glob` | `@base_tool` | `pattern: str` | Find files by pattern |
| `grep` | `@base_tool` | `pattern: str` | Search file contents |
| `list_dir` | `@base_tool` | `directory: str` | List directory tree |
| `read_file` | `@file_tool` | `filepath: str` | Read file contents |
| `write_file` | `@file_tool` | `filepath: str` | Write new file |
| `update_file` | `@file_tool` | `filepath: str` | Patch existing file |
| `react` | factory | N/A | ReAct scratchpad (state-bound) |

## Creating a New Tool

1. Create `tunacode/tools/my_tool.py`:

```python
from tunacode.tools.decorators import base_tool

@base_tool
async def my_tool(arg: str) -> str:
    """Brief description."""
    # Implementation
    return "result"
```

2. Create `tunacode/tools/prompts/my_tool_prompt.xml` with full documentation.

3. The tool is auto-discovered via lazy loading in `tunacode/tools/__init__.py`.

## Testing

Two test files validate the architecture:

- `tests/test_tool_decorators.py` - Tests decorator behavior (error routing, XML loading)
- `tests/test_tool_conformance.py` - Tests all tools follow the pattern (async, decorated, docstring, signatures)

Run with:
```bash
pytest tests/test_tool_decorators.py tests/test_tool_conformance.py -v
```

## File Structure

```
src/tunacode/tools/
├── __init__.py          # Lazy loading
├── decorators.py        # @base_tool, @file_tool
├── xml_helper.py        # XML prompt loading
├── bash.py
├── glob.py
├── grep.py
├── list_dir.py
├── read_file.py
├── write_file.py
├── update_file.py
├── todo.py              # Task management
├── submit.py            # Completion signaling
└── prompts/
    ├── bash_prompt.xml
    ├── glob_prompt.xml
    ├── grep_prompt.xml
    ├── list_dir_prompt.xml
    ├── read_file_prompt.xml
    ├── write_file_prompt.xml
    └── update_file_prompt.xml
```
