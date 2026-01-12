# Research - Parallel Tool Calling Not Working

**Date:** 2026-01-12
**Owner:** agent
**Phase:** Research

## Goal

Investigate why parallel tool calls show "Phase 3: read-only batch (1 calls)" instead of batching multiple tools together.

## Findings

### Root Cause Identified

The issue is **NOT in the batching/execution layer** - that infrastructure works correctly. The problem is that the **model is only sending ONE tool call per response**, so there's nothing to batch.

From the logs:
```
Phase 3: read-only batch (1 calls)  <- Only 1 tool received
```

The batching code at `node_processor.py:427-441` **will** execute multiple tools in parallel IF it receives them. But the model is returning single tool calls per iteration.

### Two Different Execution Paths

**Main Agent** (`main.py:386`):
- Uses `agent.iter()` for manual control over iterations
- Custom node processing extracts tool calls from `node.model_response.parts`
- Can batch and parallelize via `execute_tools_parallel()`

**Research Agent** (`research_agent.py:237` + `delegation_tools.py:86`):
- Uses `agent.run()` which abstracts away node-level access
- Pydantic-ai handles all tool execution internally
- Tools execute **sequentially** - no opportunity to batch

### Why Research Agent Can't Parallelize

1. **No node access**: `agent.run()` doesn't expose `node.model_response.parts`
2. **Internal execution**: Pydantic-ai processes tool calls inside its own loop
3. **Sequential by design**: Each tool completes before the next starts

From the code at `delegation_tools.py:86-91`:
```python
result = await research_agent.run(
    prompt,
    usage=ctx.usage,
)
return result.output
# Pydantic-ai handles ALL tool execution internally
```

### Relevant Files & Why They Matter

- `src/tunacode/core/agents/agent_components/node_processor.py` -> 4-phase batching logic (lines 342-475)
- `src/tunacode/core/agents/agent_components/tool_executor.py` -> `execute_tools_parallel()` with asyncio.gather
- `src/tunacode/core/agents/research_agent.py` -> Uses `agent.run()` not `agent.iter()`
- `src/tunacode/core/agents/delegation_tools.py:86` -> Invokes research agent
- `src/tunacode/core/agents/main.py:386` -> Main agent uses `agent.iter()` for control

### The 4-Phase Execution Strategy

From `node_processor.py:342-476`:

1. **Phase 1**: Categorize tools into buckets (research, read-only, write/execute)
2. **Phase 2**: Execute research_codebase tools
3. **Phase 3**: Execute ALL read-only tools in ONE parallel batch
4. **Phase 4**: Execute write/execute tools sequentially

Phase 3 **works** - but only receives 1 tool at a time from the research agent.

## Key Patterns / Solutions Found

### Pattern: Model needs prompting for parallel calls

The model may not be instructed to return multiple tool calls. Check system prompts for instructions like:
- "You can call multiple tools in parallel"
- "Make independent tool calls simultaneously"

### Pattern: agent.run() vs agent.iter()

| Method | Control | Parallelization |
|--------|---------|-----------------|
| `agent.run()` | Pydantic-ai internal | None (sequential) |
| `agent.iter()` | Manual node processing | Custom batching possible |

### Potential Fix: Switch research agent to agent.iter()

To enable parallel execution in research agent:

1. Replace `agent.run()` with `agent.iter()`
2. Manually iterate: `async for node in agent_run`
3. Extract tool calls from `node.model_response.parts`
4. Batch and execute via `execute_tools_parallel()`

**Trade-off**: This duplicates significant orchestration logic from `node_processor.py` (133 lines of complex state management).

## Knowledge Gaps

- Is the main agent also producing single tool calls? (logs shown appear to be from research agent based on request ID pattern)
- What does the research agent's system prompt say about parallel tool usage?
- Is this a model-specific behavior (some models better at parallel calls)?

## References

- `/root/tunacode/src/tunacode/core/agents/agent_components/node_processor.py:427-441` - Phase 3 batch execution
- `/root/tunacode/src/tunacode/core/agents/agent_components/tool_executor.py:46-110` - Parallel executor
- `/root/tunacode/src/tunacode/core/agents/research_agent.py:237-242` - Agent construction
- `/root/tunacode/src/tunacode/core/agents/delegation_tools.py:86-91` - agent.run() invocation
- `/root/tunacode/src/tunacode/core/agents/main.py:386-388` - agent.iter() usage in main agent
