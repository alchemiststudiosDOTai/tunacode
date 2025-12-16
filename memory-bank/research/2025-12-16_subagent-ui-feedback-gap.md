# Research – Subagent Workflow UI Feedback Gap

**Date:** 2025-12-16
**Owner:** research-agent
**Phase:** Research
**Git Commit:** f71d7507b496532b88335ca61550c3484e6f9fff

## Goal

Map out the subagent workflow to identify why users see "let me use the subagents..." then wait without UI feedback—causing poor UX due to lack of progress confirmation and empathy.

## Executive Summary

The UI feedback gap occurs between **line 407** (research agent execution start) and **line 410** (result check) in `node_processor.py`. During this window, `research_agent.run()` is a **black box** with no progress hooks—the spinner shows activity but doesn't distinguish parent vs. child agent work or show internal tool execution.

---

## Complete Workflow Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SUBAGENT WORKFLOW TIMELINE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  USER REQUEST                                                               │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ repl.py:133 - execute_repl_request()                             │       │
│  │   • Starts global spinner (line 144)                             │       │
│  │   • Spinner shows: "Thinking..."                                 │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ main.py - RequestOrchestrator.process_request()                  │       │
│  │   • Agent processes nodes from stream                            │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ node_processor.py:23 - _process_node()                           │       │
│  │   • Categorizes tools (lines 309-364)                            │       │
│  │   • Detects research_codebase tool                               │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│       │                                                                     │
│       ▼                                                                     │
│  ╔═════════════════════════════════════════════════════════════════╗       │
│  ║ PHASE 2: Research Agent Execution (lines 365-429)               ║       │
│  ╠═════════════════════════════════════════════════════════════════╣       │
│  ║                                                                 ║       │
│  ║  ✅ GOOD: Purple panel displayed (lines 372-397)                ║       │
│  ║     Shows: query, directories, max_files, available tools       ║       │
│  ║                                                                 ║       │
│  ║  ✅ GOOD: Spinner updated (lines 399-404)                       ║       │
│  ║     Shows: "Researching: {query_preview}..."                    ║       │
│  ║                                                                 ║       │
│  ║  ┌───────────────────────────────────────────────────────────┐  ║       │
│  ║  │                    ⚠️ THE GAP (line 407)                   │  ║       │
│  ║  │                                                           │  ║       │
│  ║  │  execute_tools_parallel(research_agent_tasks, callback)   │  ║       │
│  ║  │       │                                                   │  ║       │
│  ║  │       ▼                                                   │  ║       │
│  ║  │  delegation_tools.py:83 - research_agent.run()            │  ║       │
│  ║  │       │                                                   │  ║       │
│  ║  │       ▼                                                   │  ║       │
│  ║  │  ┌───────────────────────────────────────────────────┐    │  ║       │
│  ║  │  │ CHILD AGENT (pydantic-ai internal loop)           │    │  ║       │
│  ║  │  │                                                   │    │  ║       │
│  ║  │  │  • Calls grep ────────── NO UI FEEDBACK           │    │  ║       │
│  ║  │  │  • Calls list_dir ───── NO UI FEEDBACK            │    │  ║       │
│  ║  │  │  • Calls read_file ──── NO UI FEEDBACK            │    │  ║       │
│  ║  │  │  • Calls glob ───────── NO UI FEEDBACK            │    │  ║       │
│  ║  │  │                                                   │    │  ║       │
│  ║  │  │  User sees: Static spinner "Researching..."       │    │  ║       │
│  ║  │  │  Duration: Could be 5-30+ seconds                 │    │  ║       │
│  ║  │  │                                                   │    │  ║       │
│  ║  │  └───────────────────────────────────────────────────┘    │  ║       │
│  ║  │                                                           │  ║       │
│  ║  └───────────────────────────────────────────────────────────┘  ║       │
│  ║                                                                 ║       │
│  ║  ✅ GOOD: Completion summary (lines 410-424)                    ║       │
│  ║     Shows: "Research complete: analyzed N file(s)"              ║       │
│  ║                                                                 ║       │
│  ║  ✅ GOOD: Spinner reset (lines 426-429)                         ║       │
│  ║     Shows: "Thinking..."                                        ║       │
│  ╚═════════════════════════════════════════════════════════════════╝       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Findings

### Critical Files & Why They Matter

| File | Purpose | Gap Relevance |
|------|---------|---------------|
| [`delegation_tools.py:83`](https://github.com/alchemiststudiosDOTai/tunacode/blob/f71d7507b496532b88335ca61550c3484e6f9fff/src/tunacode/core/agents/delegation_tools.py#L83) | `research_agent.run()` call | **THE GAP** - black box with no hooks |
| [`node_processor.py:365-429`](https://github.com/alchemiststudiosDOTai/tunacode/blob/f71d7507b496532b88335ca61550c3484e6f9fff/src/tunacode/core/agents/agent_components/node_processor.py#L365-L429) | Phase 2 research agent handling | Shows BEFORE/AFTER feedback, nothing DURING |
| [`research_agent.py:77`](https://github.com/alchemiststudiosDOTai/tunacode/blob/f71d7507b496532b88335ca61550c3484e6f9fff/src/tunacode/core/agents/research_agent.py#L77) | `create_research_agent()` factory | Creates isolated agent with no UI callbacks |
| [`output.py:177-188`](https://github.com/alchemiststudiosDOTai/tunacode/blob/f71d7507b496532b88335ca61550c3484e6f9fff/src/tunacode/ui/output.py#L177-L188) | `update_spinner_message()` | Exists but never called during child execution |
| [`panels.py:124-128`](https://github.com/alchemiststudiosDOTai/tunacode/blob/f71d7507b496532b88335ca61550c3484e6f9fff/src/tunacode/ui/panels.py#L124-L128) | `research_agent()` panel | Purple panel—only used before execution |

### Root Cause Analysis

**Why the gap exists:**

1. **Isolated StateManager**: Research agent created with `StateManager()` at `delegation_tools.py:66`—parent's UI callbacks don't fire
2. **pydantic-ai Black Box**: `Agent.run()` processes tools internally with no external progress hooks
3. **No Tool Callback Propagation**: Child agent's tool calls (grep, read_file, etc.) don't trigger parent's tool_callback
4. **Static Spinner**: Message set once at line 401-404, never updated during execution

**The exact code causing the gap:**
```python
# delegation_tools.py:66 - Isolated state prevents UI updates
research_agent = create_research_agent(model, StateManager(), max_files=max_files)

# delegation_tools.py:83-86 - Black box execution
result = await research_agent.run(
    prompt,
    usage=ctx.usage,  # Only usage tracking propagated, not UI callbacks
)
```

---

## Current UI Feedback Mechanisms (Working)

| Mechanism | Location | When Shown | Status |
|-----------|----------|------------|--------|
| Global spinner | `output.py:135` | Always during agent work | ✅ Works |
| Purple research panel | `panels.py:124` | Before research execution | ✅ Works |
| Spinner message update | `output.py:177` | Before/after execution | ✅ Works |
| Completion summary | `node_processor.py:410-424` | After execution | ✅ Works |
| Green batch panel | `panels.py:117` | For parallel read-only tools | ✅ Works |

---

## The Empathy Problem

**What users experience:**

```
User: "Search the codebase for authentication patterns"

[0.0s] 🟣 Purple Panel: "RESEARCH AGENT: Search the codebase..."
[0.0s] ⏳ Spinner: "Researching: Search the codebase for auth..."
[0.1s] ... nothing ...
[5.0s] ... still nothing, just spinner ...
[15.0s] ... spinner still spinning, no updates ...
[25.0s] ... user wonders if it's stuck ...
[30.0s] ✅ "Research complete: analyzed 3 file(s), 5 finding(s)"
```

**What users should experience:**

```
User: "Search the codebase for authentication patterns"

[0.0s] 🟣 Purple Panel: "RESEARCH AGENT: Search the codebase..."
[0.0s] ⏳ Spinner: "Researching: Search the codebase for auth..."
[2.0s] ⏳ Spinner: "Searching with grep for 'auth'..."
[5.0s] ⏳ Spinner: "Found 12 matches, reading file 1/3..."
[10.0s] ⏳ Spinner: "Reading src/auth/handler.py..."
[15.0s] ⏳ Spinner: "Reading file 2/3: src/middleware/auth.py..."
[25.0s] ⏳ Spinner: "Analyzing findings..."
[30.0s] ✅ "Research complete: analyzed 3 file(s), 5 finding(s)"
```

---

## Key Patterns / Solutions Found

### Pattern 1: Tool Callback Injection
**Location:** `node_processor.py:431-483` (batch execution)
**Relevance:** Shows how to update UI during parallel tool execution—could be adapted for child agent

### Pattern 2: Streaming Panel
**Location:** `panels.py:131-401` (`StreamingAgentPanel`)
**Relevance:** Live-updating panel with asyncio.Lock for concurrent safety—could show child agent progress

### Pattern 3: State Machine Logging
**Location:** `response_state.py`
**Relevance:** State transitions logged when `show_thoughts` enabled—could extend to child agent states

---

## Knowledge Gaps

1. **pydantic-ai hooks**: Does pydantic-ai support progress/tool callbacks? Need to check their docs
2. **Performance impact**: Would adding UI callbacks to every child tool call cause latency?
3. **Parallel agents**: How to handle UI updates when multiple research agents run concurrently?
4. **Cancellation**: If user cancels during gap, how is child agent terminated?

---

## Recommended Next Steps

### Option A: Tool Callback Propagation (Moderate Complexity)
Pass parent's `tool_callback` to child agent, emit events for each tool call.

```python
# delegation_tools.py - conceptual
research_agent = create_research_agent(
    model,
    state_manager,  # Use parent's state_manager
    max_files=max_files,
    on_tool_call=lambda tool_name: ui.update_spinner(f"Child: {tool_name}")
)
```

### Option B: Polling Progress (Low Complexity)
Background task polls child agent state and updates spinner periodically.

### Option C: Live Research Panel (High Complexity)
Create dedicated `ResearchProgressPanel` that shows real-time tool execution like `StreamingAgentPanel`.

---

## References

- [`delegation_tools.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/f71d7507b496532b88335ca61550c3484e6f9fff/src/tunacode/core/agents/delegation_tools.py) - Main delegation logic
- [`node_processor.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/f71d7507b496532b88335ca61550c3484e6f9fff/src/tunacode/core/agents/agent_components/node_processor.py) - Tool categorization and UI orchestration
- [`research_agent.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/f71d7507b496532b88335ca61550c3484e6f9fff/src/tunacode/core/agents/research_agent.py) - Research agent factory
- [`output.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/f71d7507b496532b88335ca61550c3484e6f9fff/src/tunacode/ui/output.py) - Spinner management
- [`panels.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/f71d7507b496532b88335ca61550c3484e6f9fff/src/tunacode/ui/panels.py) - Panel display components
- [pydantic-ai Agent docs](https://ai.pydantic.dev/agents/) - For understanding Agent.run() internals
