---
title: "Subagent UI Feedback Gap - Plan"
phase: Plan
date: "2025-12-16T14:30:00"
owner: "claude-agent"
parent_research: "memory-bank/research/2025-12-16_subagent-ui-feedback-gap.md"
git_commit_at_plan: "f71d750"
tags: [plan, subagent, ui-feedback, coding]
---

## Goal

- **Singular Outcome**: Users see real-time spinner updates during child agent execution showing which tool is currently running (e.g., "Searching with grep...", "Reading file 1/3...").

- **Non-goals**:
  - No new UI panels or complex visualizations
  - No architectural changes to pydantic-ai
  - No changes to research agent's core logic or tools

## Scope & Assumptions

**In scope:**
- Modify `delegation_tools.py` to use `run_stream_events()` instead of `run()`
- Pass parent's `state_manager` to enable spinner updates
- Consume `FunctionToolCallEvent` to update spinner messages

**Out of scope:**
- Changes to `research_agent.py` factory function signature
- New UI components
- Parallel agent UI coordination (single agent only for now)

**Assumptions:**
- pydantic-ai's `run_stream_events()` yields `FunctionToolCallEvent` for each tool call
- `update_spinner_message()` is safe to call from async event loop
- Performance impact of event streaming is negligible

## Deliverables

1. Modified `delegation_tools.py` with event-streaming execution
2. Helper function for tool name -> user-friendly message mapping
3. Unit test validating spinner update mechanism

## Readiness

**Preconditions:**
- [x] pydantic-ai supports `run_stream_events()` with `FunctionToolCallEvent` (verified)
- [x] `update_spinner_message()` exists and works (verified at `output.py:177`)
- [x] StateManager can be passed through delegation chain

## Milestones

- **M1**: Skeleton - Add streaming infrastructure to delegation_tools.py
- **M2**: Core logic - Consume events and update spinner
- **M3**: Feature completion - Add user-friendly tool messages
- **M4**: Test - Add integration test for UI callback

## Work Breakdown (Tasks)

### Task 1: Add tool message mapping function
**Summary:** Create helper to convert tool names to user-friendly spinner messages
**Owner:** agent
**Dependencies:** None
**Target:** M3
**Files:** `src/tunacode/core/agents/delegation_tools.py`
**Acceptance:** Function returns readable strings for grep, glob, list_dir, read_file

```python
def _get_tool_spinner_message(tool_name: str, args: dict) -> str:
    """Map tool name to user-friendly spinner message."""
    messages = {
        "grep": f"Searching for '{args.get('pattern', '...')}'...",
        "glob": f"Finding files matching '{args.get('pattern', '...')}'...",
        "list_dir": f"Listing directory '{args.get('path', '.')}'...",
        "limited_read_file": f"Reading {args.get('file_path', 'file')}...",
    }
    return messages.get(tool_name, f"Running {tool_name}...")
```

---

### Task 2: Modify create_research_codebase_tool to accept UI callback
**Summary:** Add optional `on_tool_call` callback parameter to factory function
**Owner:** agent
**Dependencies:** Task 1
**Target:** M1
**Files:** `src/tunacode/core/agents/delegation_tools.py`
**Acceptance:** Factory accepts callback, closure captures it

```python
def create_research_codebase_tool(state_manager: StateManager, on_tool_call: Callable | None = None):
```

---

### Task 3: Replace run() with run_stream_events() and consume FunctionToolCallEvent
**Summary:** Use event streaming to detect tool calls and trigger spinner updates
**Owner:** agent
**Dependencies:** Task 2
**Target:** M2
**Files:** `src/tunacode/core/agents/delegation_tools.py`
**Acceptance:** Each tool call during research updates spinner message

**Implementation approach:**
```python
async with research_agent.run_stream_events(prompt, usage=ctx.usage) as stream:
    async for event in stream:
        if isinstance(event, FunctionToolCallEvent) and on_tool_call:
            tool_name = event.tool_name
            tool_args = event.args  # or parse from event
            message = _get_tool_spinner_message(tool_name, tool_args)
            await on_tool_call(message)
    result = await stream.get_result()
```

---

### Task 4: Wire up callback in node_processor.py
**Summary:** Pass spinner update callback when creating research tool
**Owner:** agent
**Dependencies:** Task 3
**Target:** M2
**Files:** `src/tunacode/core/agents/agent_components/node_processor.py` (or wherever tool is registered)
**Acceptance:** Callback updates spinner via `ui.update_spinner_message()`

**Note:** Need to verify where `create_research_codebase_tool` is called and pass:
```python
async def research_tool_callback(message: str):
    await ui.update_spinner_message(f"[bold {colors.accent}]{message}[/bold {colors.accent}]", state_manager)

research_tool = create_research_codebase_tool(state_manager, on_tool_call=research_tool_callback)
```

---

### Task 5: Add test for tool callback invocation
**Summary:** Test that streaming execution triggers callbacks for tool events
**Owner:** agent
**Dependencies:** Task 3
**Target:** M4
**Files:** `tests/core/agents/test_delegation_tools.py` (new or existing)
**Acceptance:** Mock callback receives expected tool names during simulated research

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `run_stream_events()` API differs from expected | High | Verify exact event type names in pydantic-ai source |
| Event args format varies by tool | Medium | Defensive `.get()` with fallbacks |
| Spinner update race conditions | Low | Single agent execution, sequential events |
| Performance overhead from event streaming | Low | Events are lightweight; measure if needed |

## Test Strategy

- **Task 5 test only**: Mock pydantic-ai agent, verify callback receives tool names
- No additional tests for UI rendering (manual verification sufficient)

## References

- Research: `memory-bank/research/2025-12-16_subagent-ui-feedback-gap.md`
- pydantic-ai events: `FunctionToolCallEvent`, `run_stream_events()`
- Spinner API: `src/tunacode/ui/output.py:177` (`update_spinner_message`)
- Delegation: `src/tunacode/core/agents/delegation_tools.py:83`

## Final Gate

- **Plan path:** `memory-bank/plan/2025-12-16_14-30-00_subagent-ui-feedback.md`
- **Milestone count:** 4
- **Tasks ready for coding:** 5

**Next command:** `/ce:execute "memory-bank/plan/2025-12-16_14-30-00_subagent-ui-feedback.md"`
