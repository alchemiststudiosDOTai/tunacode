# Research – ReAct Loop Agent Implementation
**Date:** 2025-09-17 17:14:35
**Owner:** context-engineer:research
**Phase:** Research

## Goal
Research existing codebase architecture to implement a ReAct loop agent with manager-worker parallel execution pattern using minimal changes.

## Findings

### Existing Agent Architecture
- **Main Entry Point**: `src/tunacode/core/agents/main.py:process_request()` function handles agent execution
- **Agent Factory**: `src/tunacode/core/agents/agent_components/agent_config.py:get_or_create_agent()` creates and caches agents
- **Caching Strategy**: Two-level caching (session-level and module-level) with version-based invalidation
- **Tool Integration**: Tools are registered as `Tool` objects with retry policies and strict validation

### Current Agent Implementation Details
1. **Agent Creation**: Uses `get_or_create_agent(model, state_manager)` pattern with caching
2. **State Management**: `StateManager` singleton holds session state, including agents dict
3. **Tool System**: Tools are registered during agent creation based on mode (plan vs normal)
4. **Execution Loop**: `process_request()` uses async iterator pattern with `agent.iter()`

### Parallel Execution Infrastructure
- **Existing**: `execute_tools_parallel()` in `tool_executor.py` for parallel tool execution
- **Pattern**: Uses `asyncio.gather()` with configurable max parallelism
- **Tool Buffer**: Read-only tools are batched for parallel execution
- **Background Tasks**: `BackgroundTaskManager` for general async task management

### Key Files and Locations
- `src/tunacode/core/agents/main.py` - Main agent orchestration (423-601)
- `src/tunacode/core/agents/agent_components/agent_config.py` - Agent factory (124-312)
- `src/tunacode/core/agents/agent_components/tool_executor.py` - Parallel tool execution
- `src/tunacode/core/state.py` - State management system
- `src/tunacode/types.py` - Type definitions including `PydanticAgent`

### ReAct Loop Implementation Requirements
Based on the minimal change plan, we need to add:

1. **ReAct Agent Factory**: `get_or_create_react_agent(model, state_manager)`
   - Similar to existing `get_or_create_agent()`
   - Append ReAct tail to system prompt
   - Cache under `(model, 'react')` key

2. **Manager Agent Factory**: `get_or_create_manager_agent(model, state_manager)`
   - Super thin implementation
   - Never calls tools directly
   - Breaks tasks into 2-5 sub-tasks
   - Specifies scope and tool whitelist per sub-task

3. **Orchestrator Function**: ~30-40 lines
   - Async function to run manager, then workers in parallel
   - Uses `asyncio.gather()` for worker parallelism
   - Manages worker caps (max_turns, tool_budget, timeout)

### Integration Points
- **State Management**: Can leverage existing `StateManager` and `SessionState`
- **Caching**: Can extend existing `_AGENT_CACHE` pattern
- **Tool System**: Can reuse existing tool registration and execution patterns
- **Parallel Execution**: Can leverage existing `asyncio.gather()` patterns

## Implementation Strategy
1. Extend `agent_config.py` with new factory functions
2. Create new orchestrator module in `src/tunacode/core/agents/react_orchestrator.py`
3. Add ReAct tail as system prompt suffix
4. Leverage existing tool execution and parallel infrastructure

## Knowledge Gaps
- Need to determine exact ReAct prompt structure
- Need to define manager agent's task decomposition strategy
- Need to specify worker result collection format
- Need to implement budget enforcement (turns, tools, time)

## References
- `src/tunacode/core/agents/agent_components/agent_config.py` - Agent factory pattern
- `src/tunacode/core/agents/main.py` - Main execution loop
- `src/tunacode/core/agents/agent_components/tool_executor.py` - Parallel execution pattern
- `src/tunacode/core/state.py` - State management system
