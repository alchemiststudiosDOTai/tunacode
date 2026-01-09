---
title: Plan Tool Not Callable Due to Missing Registration and Signature Loss
link: plan-tool-registration-failure
type: delta
path: debug_history/
depth: 1
seams: [M, A]
ontological_relations:
  - relates_to: [[agent-config]]
  - affects: [[present_plan]]
  - fixes: [[PlanToolNotCallable]]
tags:
  - pydantic-ai
  - tool-registration
  - signature-preservation
  - plan-mode
created_at: 2026-01-09T14:49:15-06:00
updated_at: 2026-01-09T14:49:15-06:00
uuid: 9c684a00-1033-40b5-9a0f-b71ab7be07f3
---

## Summary

The agent could not call the `present_plan` tool when in plan mode because:
1. The tool was never registered with the pydantic-ai agent
2. The factory function did not preserve `__signature__`, causing schema generation failures

## Context

When users enter `/plan` mode, the agent should be able to call `present_plan` to submit implementation plans for approval. The tool was created in UI code but never passed to the agent's tool list.

## Root Cause

**Two compounding issues:**

### Issue 1: Tool Not Registered

`agent_config.py:get_or_create_agent()` builds a `tools_list` but never includes `present_plan`. The tool was created in `ui/commands/__init__.py` but that instance is disconnected from the agent.

```python
# UI creates tool (useless - never reaches agent)
present_plan = create_present_plan_tool(state_manager)

# Agent's tools_list (missing present_plan)
tools_list = [bash, glob, grep, ..., research_codebase, todowrite, ...]
```

### Issue 2: Missing Signature Preservation

`create_present_plan_tool()` returns a closure without copying `__signature__`. pydantic-ai uses `inspect.signature()` to generate JSON schemas for tool calls. Without the signature, it cannot determine parameter types.

This is the same pattern documented in `research-agent-signature-loss.md`.

## Changes

**`src/tunacode/tools/present_plan.py`:**
- Added `import inspect`
- Added signature preservation: `present_plan.__signature__ = inspect.signature(present_plan)`

**`src/tunacode/core/agents/agent_components/agent_config.py`:**
- Added import: `from tunacode.tools.present_plan import create_present_plan_tool`
- Updated `_compute_agent_version()` to include `plan_mode` in hash (cache invalidation on mode toggle)
- Added conditional tool registration when `plan_mode` is True:

```python
if plan_mode:
    present_plan = create_present_plan_tool(state_manager)
    tools_list.append(Tool(present_plan, max_retries=max_retries, strict=strict))
```

## Behavioral Impact

- Agent can now call `present_plan` when in plan mode
- Agent cache invalidates when toggling plan mode (tool availability changes)
- No change to non-plan-mode behavior

## Related Cards

- [[research-agent-signature-loss]] - same signature preservation fix pattern
- [[tool-decorator-conformance]] - tool registration standards
