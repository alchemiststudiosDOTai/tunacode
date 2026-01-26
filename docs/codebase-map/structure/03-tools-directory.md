---
title: Tools Module
path: tunacode/tools
type: directory
depth: 1
description: Agent tool implementations with authorization and retry logic
seams: [bash, grep, read_file, write_file, decorators]
---

# Tools Module (`src/tunacode/tools`)

## Where
`src/tuna/Desktop/tunacode/src/tunacode/tools/` - Agent capability implementations.

## What
Implements the **tool system** that gives the AI agent real-world capabilities:
- **File Operations**: `read_file.py`, `write_file.py`, `update_file.py`
- **Shell Execution**: `bash.py` for command-line operations
- **Search Tools**: `grep.py`, `glob.py` for code searching
- **Directory Operations**: `list_dir.py` for filesystem navigation
- **Ignore Management**: `ignore.py` for shared ignore rules
- **Web Operations**: `web_fetch.py` for HTTP requests
- **Task Management**: `todo.py` for TODO list tracking
- **Authorization**: `authorization/` for permission handling
- **Decorators**: `decorators.py` for tool wrapping and retry logic
- **Utilities**: `utils/` for tool-specific helpers

## Directory Structure
```
tools/
├── bash.py                 # Shell command execution
├── grep.py                 # Content search with regex
├── glob.py                 # File pattern matching
├── read_file.py            # File reading with limits
├── write_file.py           # File creation
├── update_file.py          # File editing via edits
├── list_dir.py             # Directory listing
├── ignore.py               # Shared ignore rules
├── web_fetch.py            # HTTP requests
├── todo.py                 # TODO list management
├── decorators.py           # Tool decorators (retry, logging)
├── xml_helper.py           # XML parsing utilities
├── authorization/          # Permission system
│   └── (authorization logic)
├── grep_components/        # Grep implementation details
│   └── (search engine parts)
├── prompts/                # Tool-specific prompts
│   └── (tool descriptions)
└── utils/                  # Tool utilities
    └── (helper functions)
```

## How
The tools module implements a **decorated function pattern**:

### Tool Implementation Pattern
Each tool follows a consistent structure:
```python
@tool_decorator(
    name="tool_name",
    description="Human-readable tool description",
    parameters={<schema>},
)
async def tool_name(arg1: type, arg2: type) -> ToolResult:
    """Tool implementation with retry logic."""
    # 1. Validate inputs
    # 2. Execute operation
    # 3. Format output
    # 4. Return structured result
```

### Decorator System (`decorators.py`)
Tools are wrapped with cross-cutting concerns:
- **Retry Logic**: Automatic retries with exponential backoff
- **Logging**: Structured logging of tool calls and results
- **Error Handling**: Consistent exception conversion
- **Token Tracking**: Tool usage attribution
- **Authorization**: Pre-execution permission checks

### Tool Categories

#### Filesystem Tools
- **`read_file`**: Reads file contents with size limits
  - Enforces `MAX_FILE_SIZE` from constants
  - UTF-8 decoding with error handling
  - Line range support via `offset`/`limit`

- **`write_file`**: Creates new files
  - Validates file doesn't exist
  - Requires user confirmation for destructive operations
  - Creates parent directories if needed

- **`update_file`**: Edits existing files via string replacement
  - Reads file first to verify old_string exists
  - Validates uniqueness of match
  - Atomic write operations

#### Search Tools
- **`grep`**: Searches file contents with regex
  - Ripgrep backend for performance
  - Timeout protection for broad patterns
  - Context windowing (`-A`, `-B`, `-C`)
  - Result limiting with pagination

- **`glob`**: Matches files by path patterns
  - Recursive directory traversal
  - `.gitignore` awareness
  - Result sorting by modification time

#### Execution Tools
- **`bash`**: Executes shell commands
  - Timeout enforcement
  - Working directory management
  - Background execution support
  - stdout/stderr capture

### Authorization System (`authorization/`)
Manages user consent for tool execution:
- **Tool Whitelisting**: Pre-approved tools skip confirmation
- **Permission Prompts**: UI dialogs for approval
- **Batch Authorization**: Group multiple tool approvals
- **Dangerous Operation Detection**: Extra prompts for destructive commands

### Grep Implementation (`grep_components/`)
Complex search functionality decomposed into:
- Pattern compilation and validation
- Result ranking and relevance scoring
- Context extraction and highlighting
- Performance optimization for large codebases

## Why
**Capability Abstraction**: Tools provide a clean interface between AI and system:
- **Safety**: Authorization prevents unintended destructive actions
- **Reliability**: Retry logic handles transient failures
- **Observability**: Logging enables debugging and analytics
- **Composability**: Tools can be combined for complex workflows

**Design Principles**:
1. **Idempotency**: Tools should be safely retryable
2. **Validation**: Fail fast with clear error messages
3. **Limiting**: Enforce resource limits (file size, execution time)
4. **Atomicity**: Operations complete fully or not at all
5. **User Control**: Dangerous operations require explicit approval

## Integration Points
- **Core Agents**: `tunacode.core.agents` invokes tools via function calling
- **UI**: `tunacode.ui.renderers.tools` formats tool output for display
- **Exceptions**: `tunacode.exceptions` provides `ToolExecutionError`
- **Constants**: `tunacode.constants` defines `ToolName` enum and limits

## Code Quality Notes
- **Type Safety**: Full type hints with `TypedDict` for parameters
- **Error Messages**: Rich error context with suggested fixes
- **Testing**: Each tool has dedicated test coverage
- **Documentation**: Docstrings explain usage and edge cases
- **Performance**: Efficient algorithms (ripgrep, lazy loading)

## Tool Parameters Schema
Each tool defines a JSON schema for validation:
- **Required Parameters**: Mandatory arguments
- **Optional Parameters**: Defaults provided
- **Type Validation**: Enforced at runtime
- **Description**: Human-readable parameter docs
