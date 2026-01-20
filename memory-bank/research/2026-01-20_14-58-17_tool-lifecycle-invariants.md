# Research - Tool Lifecycle Invariants (Issue #260)

**Date:** 2026-01-20
**Owner:** Claude
**Phase:** Research
**Issue:** [#260 - Document: Tool lifecycle - don't break agent loop during tool dispatch](https://github.com/alchemiststudiosDOTai/tunacode/issues/260)
**Fix Commit:** d443a283

## Goal

Document tool lifecycle invariants after the submit tool bug fix. Understand how tool dispatch interacts with the pydantic-ai iteration loop and ensure no other code paths can cause premature loop termination.

## Findings

### The Bug (Fixed in d443a283)

**What happened:**
1. Agent called `submit` tool
2. `dispatch_tools()` executed the tool AND set `response_state.task_completed = True`
3. Back in `main.py`, loop checked `task_completed` and broke immediately
4. Agent never got to generate its final response after the tool result

**The fix:**
```python
# BEFORE (broken):
if submit_requested and response_state:
    response_state.task_completed = True

# AFTER (correct):
# NOTE: submit tool is just a marker - don't set task_completed here.
# Let pydantic-ai's loop end naturally after the agent responds.
```

### Relevant Files

| File | Purpose |
|------|---------|
| [`tool_dispatcher.py:171-348`](https://github.com/alchemiststudiosDOTai/tunacode/blob/373a33c/src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py#L171-L348) | Tool categorization and execution |
| [`main.py:365-433`](https://github.com/alchemiststudiosDOTai/tunacode/blob/373a33c/src/tunacode/core/agents/main.py#L365-L433) | Main agent iteration loop |
| [`response_state.py:62-86`](https://github.com/alchemiststudiosDOTai/tunacode/blob/373a33c/src/tunacode/core/agents/agent_components/response_state.py#L62-L86) | `task_completed` property definition |
| [`state_transition.py:97-100`](https://github.com/alchemiststudiosDOTai/tunacode/blob/373a33c/src/tunacode/core/agents/agent_components/state_transition.py#L97-L100) | `is_completed()` logic |
| [`submit.py:30-39`](https://github.com/alchemiststudiosDOTai/tunacode/blob/373a33c/src/tunacode/tools/submit.py#L30-L39) | Submit tool implementation |

### Pydantic-AI Iteration Loop Lifecycle

```
1. User message arrives
         |
         v
2. agent.iter(message, message_history) context entered
         |
         v
3. FOR each node in run_handle:
   |
   +---> Model makes request (may include tool calls)
   |
   +---> process_node() dispatches tools
   |           |
   |           +---> research tools (parallel)
   |           +---> read_only tools (parallel)
   |           +---> write/execute tools (sequential)
   |
   +---> Model responds to tool results  <-- CRITICAL: must happen!
   |
   +---> Check task_completed -> break if True
   |
   +---> Loop continues or ends naturally
         |
         v
4. Loop ends when model produces final response (no more tool calls)
```

**Key insight:** The loop MUST allow step 3's "Model responds to tool results" to happen. Setting `task_completed=True` during tool dispatch skips this step.

### Where `task_completed` Is Used

| Location | Usage | Risk Level |
|----------|-------|------------|
| `main.py:415` | `if response_state.task_completed: break` | HIGH - early exit point |
| `response_state.py:62-66` | Property getter combining `_task_completed` and `is_completed()` | N/A - definition |
| `response_state.py:68-86` | Property setter | N/A - definition |
| `state_transition.py:97-100` | `is_completed()` requires RESPONSE state + `_completion_detected` | SAFE - requires explicit flag |

### Current State: No Premature Termination Possible

After the fix, **nothing sets `task_completed = True`** during the agent loop:

1. `_task_completed` private field: Never set to `True` by any code path
2. `_completion_detected`: Never set to `True` by any code path
3. Submit tool: Only returns a confirmation string, no side effects

The loop now terminates **only** through natural exhaustion when pydantic-ai yields no more nodes.

### Tool Execution Order

```python
# tool_dispatcher.py execution order:
1. research_agent_tasks     # parallel - research_codebase tool
2. read_only_tasks          # parallel - read_file, grep, glob, list_dir, etc.
3. write_execute_tasks      # SEQUENTIAL - bash, update_file, write_file
```

The submit tool is in `READ_ONLY_TOOLS`, so it executes in the parallel read-only batch.

### State Transitions During Tool Dispatch

```
USER_INPUT/ASSISTANT --> TOOL_EXECUTION --> RESPONSE
                              ^                  |
                              |                  |
                              +------------------+
                                 (can loop back)
```

Valid transitions (from `state_transition.py:110-117`):
- `USER_INPUT` -> `ASSISTANT`
- `ASSISTANT` -> `TOOL_EXECUTION` or `RESPONSE`
- `TOOL_EXECUTION` -> `RESPONSE`
- `RESPONSE` -> `ASSISTANT` (allows continuation)

## Key Patterns / Solutions Found

### Invariant 1: Tool Dispatch Must Not Control Loop Termination

Tool dispatch is step 2 in the pydantic-ai lifecycle. Setting flags that break the loop prevents step 3 (model response) from happening. The fix enforces this by removing the `task_completed = True` assignment.

### Invariant 2: Submit Is Just a Marker

The submit tool has no side effects. It returns a confirmation string that tells the model "okay, you can wrap up now." The model then produces its final response naturally.

### Invariant 3: Loop Ends By Natural Exhaustion

Pydantic-ai's `agent.iter()` yields nodes until the model produces a response without tool calls. This is the correct termination mechanism - not external flags.

### Pattern: State Machine Guards Transitions

The `ResponseState` wraps `AgentStateMachine` with explicit transition rules. This prevents invalid state changes but doesn't (and shouldn't) force loop termination.

## Action Items from Issue #260

- [ ] **Document tool lifecycle invariants** - Create `.claude/delta/tool-lifecycle.md`
- [ ] **Add test case** - Agent must be able to respond after calling submit
- [ ] **Review other places where `task_completed` is set** - DONE: No other code paths set it

## Knowledge Gaps

1. **No test coverage** - Need integration test that verifies agent can respond after submit
2. **Documentation gap** - Tool lifecycle rules not documented in codebase-map

## References

- Issue: https://github.com/alchemiststudiosDOTai/tunacode/issues/260
- Fix commit: https://github.com/alchemiststudiosDOTai/tunacode/commit/d443a283
- Gate 6 in CLAUDE.md: Exception Paths Are First-Class (same principle)
- Journal entry 2026-01-17: Dangling tool calls on user abort (related state invariant)
