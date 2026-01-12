---
title: Parallel Tool Call Execution Analysis
link: parallel-tool-call-execution
type: research
path: src/tunacode/core/agents
depth: 3
seams: [[M] module]
ontological_relations:
  - relates_to: [[tool-execution]]
  - affects: [[agent-response]]
tags:
  - parallel
  - tool-calls
  - async
  - executor
created_at: 2026-01-12T00:00:00Z
updated_at: 2026-01-12T00:00:00Z
uuid: 550e8400-e29b-41d4-a716-446655440000
---

# Research – Parallel Tool Call Execution

**Date:** 2026-01-12
**Owner:** Claude Code
**Phase:** Research

## Goal

Investigate why the agent sometimes does not make proper parallel tool calls. Analyze the tool execution flow, categorization logic, and potential issues with parallelization.


## Findings

### Three-Tier Parallelization Strategy

The codebase implements a **three-tier parallelization strategy** for tool execution:

1. **Research agent tools** - executed in parallel
2. **Read-only tools** - collected and executed in one parallel batch
3. **Write/execute tools** - executed sequentially

### Key Files

| File | Purpose |
|------|---------|
| `src/tunacode/core/agents/agent_components/node_processor.py:341-436` | Smart batching orchestration |
| `src/tunacode/core/agents/agent_components/tool_executor.py:44-101` | Parallel execution with retry |
| `src/tunacode/core/agents/agent_components/tool_buffer.py` | Tool buffering (available but unused in main flow) |
| `src/tunacode/core/agents/main.py:494-506` | Finalize buffered tasks at iteration end |
| `src/tunacode/constants.py:74-91` | Tool categorization definitions |
| `src/tunacode/core/agents/agent_components/agent_config.py` | Agent configuration and tool registration |

### Tool Categorization (`constants.py:74-91`)

```python
READ_ONLY_TOOLS = [
    ToolName.READ_FILE,
    ToolName.GREP,
    ToolName.LIST_DIR,
    ToolName.GLOB,
    ToolName.REACT,
    ToolName.RESEARCH_CODEBASE,
    ToolName.WEB_FETCH,
]

WRITE_TOOLS = [
    ToolName.WRITE_FILE,
    ToolName.UPDATE_FILE,
]

EXECUTE_TOOLS = [
    ToolName.BASH,
]
```

### Execution Flow (`node_processor.py:341-436`)

1. **Phase 1: Collect and categorize** (lines 366-411)
   - Iterate through `node.model_response.parts`
   - Categorize tools into `read_only_tasks`, `research_agent_tasks`, `write_execute_tasks`

2. **Phase 2: Execute research agent** (lines 414-421)
   - Call `execute_tools_parallel(research_agent_tasks, tool_callback)`

3. **Phase 3: Execute read-only tools** (lines 424-436)
   - Call `execute_tools_parallel(read_only_tasks, tool_callback)`
   - All read-only tools run in ONE parallel batch

4. **Phase 4: Execute write/execute tools** (lines 439-446)
   - Sequential execution via `await tool_callback(part, node)`

### Parallel Executor (`tool_executor.py:44-101`)

```python
async def execute_tools_parallel(
    tool_calls: list[tuple[Any, Any]], callback: ToolCallback
) -> list[Any]:
    max_parallel = int(os.environ.get("TUNACODE_MAX_PARALLEL", os.cpu_count() or 4))

    async def execute_with_retry(part, node):
        for attempt in range(1, TOOL_MAX_RETRIES + 1):
            try:
                result = await callback(part, node)
                return result
            except NON_RETRYABLE_ERRORS:
                raise
            except Exception:
                if attempt == TOOL_MAX_RETRIES:
                    raise
                backoff = _calculate_backoff(attempt)
                await asyncio.sleep(backoff)

    # Execute in batches if > max_parallel, else direct parallel
    if len(tool_calls) > max_parallel:
        # Batching logic
    else:
        tasks = [execute_with_retry(part, node) for part, node in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Check for errors - raise the first one
        for result in results:
            if isinstance(result, Exception):
                raise result
```

## Key Patterns Found

1. **Batching vs Buffering**: The code uses direct categorization (`node_processor.py:366-411`) rather than the `ToolBuffer` class. The `ToolBuffer` exists (`tool_buffer.py:6-45`) but appears unused for the main flow.

2. **Sequential Write/Execute**: Write tools (`write_file`, `update_file`) and execute tools (`bash`) are always sequential to prevent race conditions on file system state.

3. **Retry with Non-Retryable Errors**: The executor distinguishes between retriable errors and fatal ones (`tool_executor.py:24-34`).

## Root Causes for Improper Parallel Execution

### Issue 1: Missing `react` Tool Registration

The `react` tool is listed in `READ_ONLY_TOOLS` but is **NOT registered** as a tool in `agent_config.py`:

- `constants.py:79` includes `ToolName.REACT` in `READ_ONLY_TOOLS`
- `agent_config.py:420-430` does NOT include `react` in the full tool set

This means if the LLM attempts to call `react` as a tool, it will fail silently or be unrecognized.

### Issue 2: `present_plan` Not in Read-Only Category

The `present_plan` tool is registered in `agent_config.py:448-449` but is **NOT** in `READ_ONLY_TOOLS`:

- `agent_config.py` registers `present_plan` tool
- `constants.py:74-82` does NOT include `present_plan`

This causes `present_plan` to be treated as a write/execute tool, executing sequentially instead of in parallel.

### Issue 3: Error Propagation in Parallel Batches

In `tool_executor.py:97-100`:

```python
results = await asyncio.gather(*tasks, return_exceptions=True)
# Check for errors - raise the first one
for result in results:
    if isinstance(result, Exception):
        raise result
```

If any tool raises an exception in the parallel batch, the error is raised immediately, potentially leaving other tools unexecuted or partially complete.

### Issue 4: ToolBuffer Unused

The `ToolBuffer` class exists but is not actively used:
- Created in `main.py:375` as `tool_buffer = ac.ToolBuffer()`
- Passed to `_process_node()` but tools are passed directly to executor
- Only `_finalize_buffered_tasks()` at `main.py:494-506` uses it, which is a cleanup path

## Knowledge Gaps

1. **Fallback tool parsing**: The `_extract_fallback_tool_calls()` function handles non-standard formats (Qwen2-style XML, Hermes-style), but unclear if this affects parallelization.

2. **pydantic-ai integration**: How pydantic-ai handles multiple tool calls in a single response - does it batch them or expect sequential returns?

3. **Tool name comparison**: The categorization uses `part.tool_name in READ_ONLY_TOOLS` where `READ_ONLY_TOOLS` contains `ToolName` enum values. This works because `ToolName` is a `str` enum, but could be a source of bugs if not consistently applied.

## References

- `src/tunacode/core/agents/agent_components/node_processor.py` - Node processing and tool categorization
- `src/tunacode/core/agents/agent_components/tool_executor.py` - Parallel execution implementation
- `src/tunacode/constants.py` - Tool categorization definitions
- `src/tunacode/core/agents/agent_components/agent_config.py` - Tool registration
- `src/tunacode/core/agents/main.py` - Main agent loop and orchestration
