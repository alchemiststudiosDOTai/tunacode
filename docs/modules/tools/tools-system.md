---
title: Tools System
summary: Architecture and implementation of the native tinyagent tool system used by TunaCode's LLM agent.
read_when: Understanding how tools are implemented, registered, and executed in the agent loop.
depends_on: [types, infrastructure, configuration, core]
feeds_into: [core]
when_to_read:
  - Understanding how tools are implemented
  - Understanding how tools are registered
  - Understanding how tools are executed in the agent loop
last_updated: "2026-04-04"
---

# Tools System

## Overview

The tools system exposes TunaCode's capabilities to the LLM agent as callable functions. Each tool is a native tinyagent `AgentTool` with JSON-schema parameter definitions and an `execute()` implementation that runs at runtime.

The system provides 6 core tools: `bash`, `discover`, `read_file`, `hashline_edit`, `web_fetch`, and `write_file`.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Loop (tinyagent)                   │
├─────────────────────────────────────────────────────────────────┤
│  Agent decides to call a tool → tinyagent routes to execute()  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Tool Layer (src/tunacode/tools/)              │
├─────────────┬─────────────┬─────────────┬──────────┬────────────┤
│   bash.py   │ discover.py │ read_file.py│hashline  │ web_fetch  │
│             │             │             │ _edit.py │            │
├─────────────┴─────────────┴─────────────┴──────────┴────────────┤
│                      Supporting Modules                          │
├─────────────┬─────────────┬─────────────┬──────────┬────────────┤
│ line_cache  │   ignore    │  utils/     │cache_    │            │
│             │             │  ripgrep    │accessors │            │
└─────────────┴─────────────┴─────────────┴──────────┴────────────┘
```

## Tool Registry

| Tool | File | Purpose |
|------|------|---------|
| `bash` | `bash.py` | Shell command execution |
| `discover` | `discover.py` | Semantic repository search |
| `read_file` | `read_file.py` | Read file with hash-tagged lines |
| `hashline_edit` | `hashline_edit.py` | Validate-and-edit files |
| `web_fetch` | `web_fetch.py` | Fetch public web content |
| `write_file` | `write_file.py` | Create new files |

## Tool Contract

Each tool implements the tinyagent `AgentTool` contract:

1. **JSON Schema Parameters** -- Defines required/optional inputs with types and descriptions
2. **execute() Method** -- Signature: `execute(tool_call_id, args, signal, on_update)`
   - `tool_call_id`: Unique identifier for this tool call
   - `args`: Dictionary of parameter values
   - `signal`: Abort signal for cancellation
   - `on_update`: Callback for streaming progress

3. **Return Type** -- Returns `AgentToolResult` with structured content

## Registration Pipeline

Tools are registered in `src/tunacode/core/agents/agent_components/agent_config.py`:

1. `_build_tools()` imports native tool objects directly from each module
2. `_apply_tool_concurrency_limit()` wraps tools with a shared semaphore
3. Tools are handed to the tinyagent agent constructor

```python
# Simplified flow
def _build_tools() -> list[AgentTool]:
    from tunacode.tools import bash, discover, read_file, hashline_edit, web_fetch, write_file
    return [bash.tool, discover.tool, read_file.tool, hashline_edit.tool, web_fetch.tool, write_file.tool]

def _apply_tool_concurrency_limit(tools: list[AgentTool], limit: int) -> list[AgentTool]:
    semaphore = asyncio.Semaphore(limit)
    # wrap each tool...
```

## Hashline Contract (Safe Edit Path)

The `read_file` to `hashline_edit` flow enforces edit safety:

### read_file

- Reads file with hash-tagged lines: `"line_number:hash|content"`
- Caches the read window in `line_cache.py`
- Returns wrapped output: `<file>...</file>`

### hashline_edit

- Validates `<line>:<hash>` references against cached window
- Rejects edits to lines not in the current cache
- Rejects edits if the hash no longer matches (file changed)
- Returns unified diff

This prevents the model from:
- Editing lines it hasn't read
- Overwriting concurrent external changes
- Making edits that conflict with the file state

See [hashline-subsystem.md](hashline-subsystem.md) for full details.

## Supporting Modules

### line_cache.py
Validates read-then-edit flows. Maintains a window of hash-tagged lines.

### ignore.py / ignore_manager.py
Gitignore rule parsing and matching for discovery.

### utils/ripgrep.py
Ripgrep executor for fast text search. Handles platform binaries and caching.

### utils/discover_pipeline.py
Semantic search pipeline that extracts terms, builds glob patterns, and evaluates file relevance.

### cache_accessors/
Typed caches for ripgrep results, XML prompts, and gitignore state.

## Execution Flow

```
1. LLM decides: "I need to read src/main.py"
2. tinyagent routes to read_file.execute()
3. read_file reads file, generates hashes, caches window
4. Returns: [("file", "123:abc|line content...")]
5. LLM decides: "I'll edit line 123"
6. tinyagent routes to hashline_edit.execute()
7. hashline_edit validates hash matches cached value
8. On match: apply edit, update cache, return diff
9. On mismatch: reject with error message
```

## Configuration

Tool behavior is influenced by configuration:

- **Command limits** -- `src/tunacode/configuration/limits.py` controls bash output truncation
- **Timeout ranges** -- bash enforces 1-600 second timeout range
- **File size limits** -- read_file rejects files over 100KB
- **Concurrency limits** -- shared semaphore limits parallel tool executions

## Testing

Tool conformance tests verify:
- Parameter validation
- Hash verification in edit flows
- Abort signal handling
- Result serialization

See `tests/unit/tools/` and `tests/integration/tools/`.
