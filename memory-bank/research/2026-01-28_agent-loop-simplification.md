# Research – Agent Loop Simplification

**Date:** 2026-01-28
**Owner:** claude-opus
**Phase:** Research

## Goal

Understand the current agent loop architecture to identify paths for decoupling from pydantic-ai and creating a simpler, more maintainable basic loop.

## Key Insight

**53% of agent loop code is debugging/instrumentation, not core logic.**

| File | Total Lines | Core Logic | Debug/Instrumentation |
|------|-------------|------------|----------------------|
| streaming.py | 385 | 30 | 355 |
| tool_dispatcher.py | 353 | 100 | 253 |
| tool_executor.py | 142 | 60 | 82 |
| orchestrator.py | 301 | 150 | 151 |
| main.py (relevant) | ~300 | 200 | 100 |
| **Total** | **1,481** | **540** | **941** |

## Findings

### Current Architecture (pydantic-ai driven)

```
User Request
    ↓
RequestOrchestrator._run_impl()
    ↓
┌─────────────────────────────────────────┐
│  async with agent.iter() as run_handle: │  ← pydantic-ai controls loop
│    async for node in run_handle:        │
│      - stream tokens (if model request) │
│      - process node (extract tools)     │
│      - dispatch tools (parallel exec)   │
│      - check completion                 │
└─────────────────────────────────────────┘
    ↓
Persist messages
```

### What pydantic-ai gives us

1. **Node iteration** - Opaque node types (`ModelRequestNode`, `CallToolNode`, etc.)
2. **Streaming protocol** - `node.stream()` yields `PartDeltaEvent` / `TextPartDelta`
3. **Tool execution** - pydantic-ai calls registered tool functions directly
4. **Retry logic** - Built-in retry with `RetryConfig` and `AsyncTenacityTransport`
5. **Message history** - `agent_run.all_messages()` for persistence

### What tunacode adds on top

1. **Pre-loop cleanup** - 50+ lines sanitizing corrupt history from aborts
2. **Streaming wrapper** - 385 lines (355 debug) to forward token deltas
3. **Tool dispatch** - Registry tracking, fallback parsing, parallel batching
4. **State tracking** - `ResponseState`, `ToolRegistry`, empty response handling
5. **Error recovery** - `UserAbortError` cleanup, dangling tool call removal

### Core Complexity Sources

| Source | Lines | Why Complex |
|--------|-------|-------------|
| History cleanup | ~100 | Multiple passes to fix corrupt state from aborts |
| Node type guards | ~50 | `Agent.is_model_request_node()`, attribute checks |
| Streaming indirection | ~355 | Debug logging, prefix seeding, overlap detection |
| Tool callback no-op | ~30 | Callback exists but pydantic-ai executes tools |
| Fallback parsing | ~75 | Handle models without native tool calls |

## Relevant Files

| File | Purpose |
|------|---------|
| `src/tunacode/core/agents/main.py` | Main loop, RequestOrchestrator |
| `src/tunacode/core/agents/agent_components/agent_config.py` | Agent creation, model providers |
| `src/tunacode/core/agents/agent_components/streaming.py` | Token streaming |
| `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py` | Node processing |
| `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py` | Tool dispatch |
| `src/tunacode/core/agents/agent_components/tool_executor.py` | Parallel execution |
| `src/tunacode/core/agents/resume/sanitize.py` | History cleanup |

## Pydantic-AI Integration Depth

### Deep Integration (7 files in core/agents/)
- `Agent()` constructor, `agent.iter()`, `agent.run()`
- `ModelRetry` exception, node types, streaming protocol
- Message history via `agent_run.all_messages()`

### Medium Integration (4 files in types/utils/)
- Type wrappers in `types/pydantic_ai.py`
- Adapter layer in `utils/messaging/adapter.py`

### Light Integration (9 tool files + 1 decorator)
- Only `ModelRetry` exception import

**Total: 37 files with pydantic-ai imports**

## Grimp Dependency Analysis

```
Layer Order:
ui → core → infrastructure → tools → utils → configuration → constants → exceptions → types
```

Key insight from grimp: `core.agents.agent_config` directly imports all 9 tool modules to register them with pydantic-ai's `Agent()`. This tight coupling exists because pydantic-ai needs tool functions at agent creation time.

## Basic Loop Alternative

A minimal loop without pydantic-ai would look like:

```python
async def run_agent(message: str, history: list[dict]) -> str:
    while True:
        # 1. Make API call
        response = await client.chat.completions.create(
            model=model,
            messages=history + [{"role": "user", "content": message}],
            tools=tool_schemas,
            stream=True,
        )

        # 2. Stream response
        content, tool_calls = await stream_response(response)
        history.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        # 3. If no tool calls, done
        if not tool_calls:
            return content

        # 4. Execute tools
        for tool_call in tool_calls:
            result = await execute_tool(tool_call)
            history.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})

        # 5. Continue loop for next model response
```

**Estimated core logic: ~100 lines** (vs current ~540 lines)

## What We'd Lose

1. **pydantic-ai retry** - Would need our own (we have `tool_executor.py` logic)
2. **Model abstraction** - Would need to handle Anthropic/OpenAI differences
3. **Tool validation** - Would need pydantic schemas ourselves
4. **Structured outputs** - Would need to parse responses ourselves

## What We'd Gain

1. **Direct control** - No opaque node iteration
2. **Simpler debugging** - No pydantic-ai internals to trace
3. **Less code** - ~400 lines less
4. **Flexibility** - Can customize loop behavior directly

## Knowledge Gaps

1. **Anthropic streaming differences** - Their API differs from OpenAI
2. **Tool call format differences** - Anthropic uses different structure
3. **Retry semantics** - What does pydantic-ai's `ModelRetry` actually do internally?
4. **History validation** - What checks does pydantic-ai do on message history?

## Simplification Options

### Option A: Keep pydantic-ai, extract debug code
- Move 941 lines of debug/instrumentation behind feature flags
- Core loop stays ~540 lines but feels cleaner
- **Effort: Low (1-2 days)**

### Option B: Replace iteration model only
- Keep `Agent` for tool registration and validation
- Replace `agent.iter()` with direct API calls
- Use pydantic-ai just for type definitions
- **Effort: Medium (3-5 days)**

### Option C: Full decoupling
- Remove pydantic-ai entirely
- Use OpenAI/Anthropic SDKs directly
- Build thin adapter for model differences
- **Effort: High (1-2 weeks)**

## Recommendation

**Option B** strikes the best balance:
- Keep pydantic-ai's tool validation and type definitions
- Replace the opinionated iteration model with direct control
- Maintain 37-file compat via adapter layer

The key insight is that pydantic-ai's value is in **types and validation**, not in **loop orchestration**. The loop orchestration is where our complexity lives.

## References

- `docs/architecture/dependencies/DEPENDENCY_LAYERS.md` - Grimp baseline
- `memory-bank/research/2026-01-27_alchemy-rs-migration.md` - Previous migration research
- User's ASCII diagram in this conversation - Current architecture overview
