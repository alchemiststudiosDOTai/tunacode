---
title: Tool registry and typed todo alignment
link: tool-registry-todo-alignment
type: delta
path: src/tunacode/types/tool_registry.py
depth: 0
seams: [S] state
ontological_relations:
  - relates_to: [[tool-call-lifecycle]]
  - affects: [[runtime-state]]
  - affects: [[task-state]]
tags:
  - tool-calls
  - todos
  - state
  - registry
created_at: 2026-01-25T23:09:13Z
updated_at: 2026-01-25T23:09:13Z
uuid: 0ea0d90a-081b-4b9a-be37-4a325d4c7914
---

## Summary

Introduced a ToolCallRegistry as the single source of truth for tool call lifecycle data and migrated session todos to typed TodoItem storage with explicit serialization. This removes duplicated tool call tracking and aligns runtime todo state with canonical types.

## Context

Tool calls were tracked in separate runtime lists and arg caches, while todos were stored as ad-hoc dicts. Both patterns increased drift risk and made lifecycle semantics inconsistent across the session.

## Changes

- **Tool registry**: Added `ToolCallRegistry` and wired tool dispatch, tool execution failure tracking, and tool return completion updates to the registry.
- **Runtime state**: Removed `tool_calls` and `tool_call_args_by_id`, replacing them with `runtime.tool_registry`.
- **Todo alignment**: Stored todos as `TodoItem` instances, updated todo tools to emit typed items, and normalized session serialization/deserialization.
- **Docs**: Refreshed codebase-map and refactor docs to reflect registry ownership and typed todos.

## Behavioral Impact

**What users notice:**
- Tool lifecycle data is consistent across executions and JSON export paths.
- Todo state is typed and validated consistently in todowrite/todoread.

**What didn't change:**
- Tool execution flow and message history semantics remain the same.
- Legacy session files still load via dict-to-TodoItem conversion.

## Related Cards

- [[orphaned-retry-prompt-dangling-cleanup]]
