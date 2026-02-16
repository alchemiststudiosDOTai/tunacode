---
title: Tools Layer
summary: LLM-callable tool implementations, decorator framework, and supporting subsystems (grep engine, LSP, parsing).
read_when: Adding a new tool, modifying tool error handling, or changing how tool schemas are generated.
depends_on: [types, infrastructure, configuration]
feeds_into: [core]
---

# Tools Layer

**Package:** `src/tunacode/tools/`

## What

Every capability the agent can invoke during a conversation. Each tool is an async function decorated with `@base_tool` or `@file_tool`, then converted to a tinyagent `AgentTool` via `to_tinyagent_tool()`.

## Key Files

### Tool Implementations

| File | Tool Name | Purpose |
|------|-----------|---------|
| `bash.py` | `bash` | Execute shell commands with timeout and output capture. |
| `glob.py` | `glob` | Find files by glob pattern, respecting ignore rules. |
| `grep.py` | `grep` | Regex search across files using ripgrep. |
| `read_file.py` | `read_file` | Read file contents with optional line range. |
| `write_file.py` | `write_file` | Create or overwrite a file. |
| `update_file.py` | `update_file` | Apply a targeted string replacement in a file. |
| `list_dir.py` | `list_dir` | List directory contents with file metadata. |
| `web_fetch.py` | `web_fetch` | Fetch and summarize a web page. |

### Framework

| File | Purpose |
|------|---------|
| `decorators.py` | `@base_tool` -- wraps tools with consistent error handling (`ToolRetryError` passthrough, catch-all to `ToolExecutionError`). `@file_tool` -- adds path-specific error mapping (`FileNotFoundError` to `ToolRetryError`, `PermissionError` to `FileOperationError`). `to_tinyagent_tool()` -- converts a decorated async function to an `AgentTool` with auto-generated OpenAI-function JSON schema. |
| `xml_helper.py` | Loads tool descriptions from XML prompt files. If a tool has a matching XML file, its docstring is replaced with the XML content at decoration time. |
| `ignore.py` | Core ignore-pattern matching logic. |
| `ignore_manager.py` | Manages the full ignore stack (built-in + `.gitignore` + user overrides). |

### Grep Engine (`grep_components/`)

| File | Purpose |
|------|---------|
| `file_filter.py` | Decides which files to search based on ignore rules and include patterns. |
| `pattern_matcher.py` | Regex compilation and matching with timeout protection. |
| `result_formatter.py` | Formats grep results for the LLM (line numbers, context lines, truncation). |
| `search_result.py` | `SearchResult` dataclass for a single match. |

### LSP (`lsp/`)

| File | Purpose |
|------|---------|
| `client.py` | LSP client for language-server communication. |
| `diagnostics.py` | Fetch and format diagnostics from the LSP server. |
| `servers.py` | Server configuration and lifecycle management. |

### Parsing (`parsing/`)

| File | Purpose |
|------|---------|
| `command_parser.py` | Parse slash commands from user input. |
| `json_utils.py` | Tolerant JSON parsing for LLM output. |

### Utilities (`utils/`)

| File | Purpose |
|------|---------|
| `formatting.py` | Text formatting helpers (truncation, line numbering). |
| `ripgrep.py` | Ripgrep binary detection and invocation. |
| `text_match.py` | Fuzzy and exact text matching for update operations. |

### Cache Accessors (`cache_accessors/`)

| File | Purpose |
|------|---------|
| `ignore_manager_cache.py` | Cached ignore-manager instance. |
| `ripgrep_cache.py` | Cached ripgrep binary path. |
| `xml_prompts_cache.py` | Cached XML prompt content. |

## How

Tool registration flow:
1. `agent_config.py::_build_tools()` calls `to_tinyagent_tool()` on each decorated tool function.
2. `to_tinyagent_tool()` introspects the function signature to build an OpenAI-function JSON schema.
3. The tool's docstring (possibly replaced by XML prompt content) becomes the tool description the model sees.
4. At runtime, tinyagent calls `AgentTool.execute(tool_call_id, args, signal, on_update)`.
5. The adapter binds `args` to the function signature, checks for abort signal, calls the tool, and wraps the result in `AgentToolResult`.

Error contract:
- `ToolRetryError` -- model should try again with corrected arguments (surfaces as tool error to model).
- `ToolExecutionError` -- hard failure, reported to user.
- `FileOperationError` -- file-specific hard failure.

## Why

The decorator pattern means tool authors only write the business logic. Error handling, schema generation, and abort-signal checking are handled uniformly. The XML prompt system lets tool descriptions be edited without touching Python code.
