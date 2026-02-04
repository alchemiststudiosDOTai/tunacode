---
date: 2026-02-04
type: feature
scope: ui
impact: medium
---

# Stacked Tool Call UI (Tool-Call Burst Summary Widget)

## Summary

Implemented a compact "tool call stack" display to match the dream UI: when a model response dispatches many tools, the UI shows a short list of tool invocations (tool name + primary argument) instead of spamming full tool result panels.

This fixes the practical issue with return-based batching: tool *returns* arrive over time, so debouncing tool results does not reliably stack.

## Changes

### Emit tool-call start events (core)

`src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`

- When tools are dispatched for execution, we now emit a `tool_result_callback(..., status="running", args=...)` event for each tool call.
- These "running" events arrive as a tight burst (because they are emitted at dispatch time), enabling reliable stacking.

### Tool call stack widget (UI)

`src/tunacode/ui/widgets/tool_call_stack.py`

- Added `ToolCallStack`, a Textual `Static` widget that renders compact rows:
  - `▶ {tool_name:<12} {primary_arg}`
- No timestamps.
- When more than 3 tool calls are present, the widget caps to the last 3 visible calls and adds a dim indicator line (`… +N more`).

### App integration + suppression

`src/tunacode/ui/app.py`

- `on_tool_result_display()` now:
  - buffers `status="running"` messages and flushes them after a short debounce
  - mounts a `ToolCallStack` when the buffered tool-call count exceeds 3
  - suppresses detailed per-tool result panels for that stacked batch
- When <=3 tool calls are dispatched, we keep existing per-tool tool panels.

### Documentation updates

- Updated `docs/codebase-map/modules/ui-overview.md` to describe tool-call burst stacking and the new widget.

## Verification

- `uv run ruff check .`
- `uv run pytest`
