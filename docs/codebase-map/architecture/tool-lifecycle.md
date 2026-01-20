# Tool Lifecycle Invariants

## Overview

This document defines the invariants that govern tool execution within the pydantic-ai agent iteration loop. These rules exist to prevent bugs like the one fixed in [PR #246](https://github.com/alchemiststudiosDOTai/tunacode/commit/d443a283) where premature loop termination prevented the agent from responding after tool execution.

---

## The Golden Rule

**Tool dispatch must NEVER control loop termination.**

The pydantic-ai iteration loop has a 3-step lifecycle per iteration:

```
┌─────────────────────────────────────────────────────────────────┐
│ AGENT ITERATION LIFECYCLE                                       │
│                                                                 │
│  Step 1: Model Request                                          │
│          Model produces response (may include tool calls)       │
│                        │                                        │
│                        ▼                                        │
│  Step 2: Tool Dispatch                                          │
│          Tools are categorized and executed                     │
│          !! DO NOT set task_completed here !!                   │
│                        │                                        │
│                        ▼                                        │
│  Step 3: Model Response                                         │
│          Model responds to tool results  <-- MUST HAPPEN        │
│                        │                                        │
│                        ▼                                        │
│  Loop continues or ends naturally                               │
└─────────────────────────────────────────────────────────────────┘
```

Setting `task_completed=True` during Step 2 skips Step 3. The agent never gets to respond to tool results.

---

## Invariants

### Invariant 1: Tool Dispatch Is Pass-Through

Tool dispatch (`tool_dispatcher.py`) must:
- Execute tools
- Record results
- Transition state machine (ASSISTANT -> TOOL_EXECUTION -> RESPONSE)

Tool dispatch must NOT:
- Set `task_completed`
- Break the iteration loop
- Make decisions about when the agent is "done"

```python
# WRONG - breaks loop before agent can respond
if submit_requested and response_state:
    response_state.task_completed = True

# RIGHT - let loop end naturally
# (just don't set task_completed at all)
```

### Invariant 2: Submit Is Just a Marker

The `submit` tool signals intent, not completion. It:
- Returns a confirmation string
- Has NO side effects on state
- Does NOT set any flags

The agent calls submit to say "I'm ready to wrap up." The model then produces its final response naturally, and pydantic-ai stops yielding nodes.

```python
# submit.py - the entire implementation
async def submit(summary: str | None = None) -> str:
    return _format_submit_message(summary)
```

### Invariant 3: Loop Ends By Natural Exhaustion

The correct termination mechanism is pydantic-ai's natural loop exhaustion:

```python
async with agent.iter(message, message_history) as run:
    async for node in run:
        # ... process node ...
        pass
    # Loop ends here when model produces response without tool calls
```

The loop ends when the model produces a response that doesn't include tool calls. This is the ONLY correct termination path.

### Invariant 4: task_completed Is Emergency-Only

The `task_completed` flag exists but should rarely be used:

```python
# main.py:415 - early exit check
if response_state.task_completed:
    logger.info("Task completed", iteration=i)
    break
```

This flag is for edge cases (e.g., external cancellation), not normal operation. Currently, NO code path sets this flag during normal agent execution.

---

## Tool Execution Order

Tools are categorized and executed in strict order:

```
┌─────────────────────────────────────────────────────────────────┐
│ TOOL EXECUTION ORDER                                            │
│                                                                 │
│ 1. RESEARCH TOOLS (parallel)                                    │
│    └─ research_codebase                                         │
│                                                                 │
│ 2. READ-ONLY TOOLS (parallel)                                   │
│    ├─ read_file                                                 │
│    ├─ grep                                                      │
│    ├─ glob                                                      │
│    ├─ list_dir                                                  │
│    ├─ web_fetch                                                 │
│    ├─ present_plan                                              │
│    └─ submit  <-- marker only, no state changes                 │
│                                                                 │
│ 3. WRITE/EXECUTE TOOLS (sequential)                             │
│    ├─ bash                                                      │
│    ├─ write_file                                                │
│    └─ update_file                                               │
└─────────────────────────────────────────────────────────────────┘
```

Write tools are sequential to prevent race conditions on the filesystem.

---

## State Transitions

Valid state transitions during tool dispatch:

```
USER_INPUT ──────► ASSISTANT
                       │
                       ▼
              TOOL_EXECUTION
                       │
                       ▼
                  RESPONSE ◄────────┐
                       │            │
                       └────────────┘
                     (can loop back)
```

The state machine tracks WHERE we are, not WHETHER we're done. Completion is determined by loop exhaustion, not state.

---

## The Bug That Taught Us This

**Issue:** [#260](https://github.com/alchemiststudiosDOTai/tunacode/issues/260)
**Fix:** [d443a283](https://github.com/alchemiststudiosDOTai/tunacode/commit/d443a283)

Before the fix:
1. Agent called `submit` tool
2. `dispatch_tools()` set `task_completed = True`
3. Loop broke at line 415 in `main.py`
4. Agent never responded after the submit tool result

After the fix:
1. Agent calls `submit` tool
2. Tool executes and returns confirmation string
3. Loop continues
4. Model produces final response
5. Loop ends naturally (no more tool calls)

---

## Testing Requirements

Any changes to tool dispatch or loop termination must verify:

1. **Agent can respond after ANY tool** - especially submit
2. **Loop terminates naturally** - not via flags
3. **State machine doesn't block responses** - transitions are valid

Example test case:
```python
async def test_agent_responds_after_submit():
    # Agent calls submit tool
    # Verify: agent produces text response AFTER submit
    # Verify: loop ends naturally, not via task_completed
```

---

## Related Documentation

- [Conversation Turn Flow](./conversation-turns.md) - Full request lifecycle
- [Architecture Overview](./architecture.md) - System design
- [Gate 6 in CLAUDE.md](../../../CLAUDE.md) - Exception paths are first-class

---

## File References

| File | Purpose |
|------|---------|
| `src/tunacode/core/agents/main.py:365-433` | Main iteration loop |
| `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py` | Tool dispatch |
| `src/tunacode/core/agents/agent_components/response_state.py` | State tracking |
| `src/tunacode/tools/submit.py` | Submit tool (marker only) |
