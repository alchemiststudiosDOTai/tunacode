---
title: Tools Module
path: src/tunacode/tools
type: directory
depth: 1
description: Tool implementations, decorators, and authorization system
exports: [base_tool, file_tool, ToolHandler, bash, glob, grep, read_file, write_file, update_file]
seams: [M, D]
---

# Tools Module

## Purpose
Provides AI agent capabilities through a robust tool system with decorators, authorization, and specialized implementations.

## Tool Decorator System (decorators.py)

### base_tool
Foundation decorator for all tools:
- Standardizes error handling (Exception → ToolExecutionError)
- Loads tool descriptions from XML prompt files
- Ensures consistent error propagation
- Preserves ModelRetry and ToolExecutionError exceptions

### file_tool
Specialized decorator for file system tools:
- Extends base_tool functionality
- Handles file-specific errors (FileNotFoundError, PermissionError, UnicodeDecodeError)
- Fetches LSP diagnostics after writes (when writes=True)
- Provides immediate code quality feedback

**XML Prompt Files:**
- `bash_prompt.xml` - Bash tool documentation
- `read_file_prompt.xml` - Read file documentation
- `submit_prompt.xml` - Submit tool documentation
- etc.

## Authorization System (authorization/)

### ToolHandler (handler.py)
Central authorization coordinator:
- Evaluates if tool requires confirmation
- Manages user confirmation responses
- Updates tool_ignore list for future skips
- Coordinates with policy and rules

### AuthorizationPolicy (policy.py)
Aggregates authorization rules:
- Evaluates rules in priority order
- Determines if confirmation can be bypassed
- Composite pattern for flexible policies

### Authorization Rules (rules.py)

**ReadOnlyToolRule**
- Bypasses confirmation for safe read-only tools
- Covers: glob, grep, read_file, list_dir

**TemplateAllowedToolsRule**
- Respects template's allowed_tools list
- Template-specific permission grants

**YoloModeRule**
- System-wide bypass when enabled
- For advanced users requiring full automation

**ToolIgnoreListRule**
- Honors "skip future confirmations" user choice
- Persistent per-session tool approvals

### Context (context.py)
**AuthContext Dataclass:**
- **yolo_mode** - Global bypass setting
- **tool_ignore_list** - Previously approved tools
- **active_template** - Current template constraints

### Supporting Components

**factory.py** - ConfirmationRequestFactory
- Generates detailed confirmation requests
- Includes file diffs for review

**notifier.py** - ToolRejectionNotifier
- Informs agent of cancelled tool executions

**requests.py** - ToolConfirmationRequest/Response
- Data structures for confirmation flow

## Tool Implementations

### bash.py
Executes shell commands securely:
- Destructive pattern validation (blocks `rm -rf`, etc.)
- Configurable timeouts
- Stdout/stderr capture with exit codes
- Working directory management

### glob.py
Fast file pattern matching:
- Supports `**/*.py` style patterns
- Recursive searching
- .gitignore awareness
- Sorted results
- Integration with CodeIndex
- Shared ignore directory list from `utils/system/ignore_patterns.py`

### grep.py
Advanced content search:
**Search Strategies:**
- `smart` - Auto-selects best method
- `ripgrep` - Uses ripgrep binary
- `python` - Pure Python implementation
- `hybrid` - Combined approach

**Features:**
- Regex support
- Case sensitivity control
- File type filtering
- Context lines
- Output modes: content, files-only, count, JSON
- Broad pattern prevention
- Shared ignore directory list for fast-glob prefiltering

### read_file.py
Reads file contents safely:
- Line range support (offset/limit)
- Line number preservation
- Long line truncation
- Streaming line reads to avoid loading entire files into memory
- File size limits
- Encoding handling

### write_file.py
Creates new files:
- Parent directory auto-creation
- Overwrite prevention (use update_file instead)
- LSP diagnostic triggers
- Atomic writes

### update_file.py
Modifies existing files:
**Fuzzy Matching Algorithms:**
- `line-trimmed` - Whitespace-tolerant
- `indentation-flexible` - Indent-tolerant
- `block-anchor` - Multi-line block matching

**Features:**
- Diff generation
- LSP diagnostic updates
- Change validation

### list_dir.py
Lists directory contents:
- Recursive tree view
- Ignore pattern support
- Hidden file visibility
- Output size limits
- Shared ignore pattern list from `utils/system/ignore_patterns.py`

### web_fetch.py
Fetches web content:
- HTTP/HTTPS only
- HTML to plain text conversion
- Security validation (blocks private IPs)
- Content size limits
- Timeout handling

### todo.py
Task management for agents:
**Tools:**
- **todowrite** - Create/update tasks
- **todoread** - Read task list
- **todoclear** - Clear all tasks

**Task States:**
- `pending` - Not started
- `in_progress` - Currently working
- `completed` - Finished

### react.py
ReAct pattern support:
- Manages agent scratchpad
- Tracks thought process
- Structured reasoning guidance

### submit.py
Completion signaling tool:
- `submit` marks the task as complete for the orchestrator
- Optional summary text for the final response

## Tool Utilities (tools_utils/)

### text_match.py
Fuzzy matching algorithms for update_file:
- Line-trimmed matching
- Indentation-flexible matching
- Block-anchor matching

### ripgrep.py
Ripgrep integration wrapper:
- Binary detection
- Output parsing
- Error handling
- Async subprocess execution with timeouts

## Integration Points

- **core/agents/** - Tool registration and execution
- **core/agents/tool_executor.py** - Parallel execution
- **ui/renderers/** - Specialized output rendering
- **authorization/** - Permission management

## Seams (M, D)

**Modification Points:**
- Add new tool implementations
- Extend decorator system with new features
- Customize authorization rules
- Add new fuzzy matching algorithms

**Extension Points:**
- Create custom tool types
- Implement specialized authorizers
- Add tool-specific validation
- Extend prompt XML system
