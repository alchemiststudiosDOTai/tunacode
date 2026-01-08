---
title: list_dir halts agent on bad paths
link: list-dir-tool-execution-error
type: delta
path: src/tunacode/tools/list_dir.py
depth: 0
seams: [M] module
ontological_relations:
  - relates_to: [[tools]]
  - affects: [[tool-executor]]
  - fixes: [[agent-halt-on-tool-error]]
tags:
  - tools
  - error-handling
  - list_dir
  - ModelRetry
created_at: 2026-01-07T22:54:00-08:00
updated_at: 2026-01-07T23:15:00-08:00
uuid: a1b2c3d4-e5f6-7890-abcd-ef1234567890
---

## Summary

`list_dir` raised `FileNotFoundError` on non-existent directories, which `@base_tool` wrapped as `ToolExecutionError`. Since `ToolExecutionError` is in `NON_RETRYABLE_ERRORS`, the agent halted instead of letting the LLM self-correct with a valid path.

## Context

Surfaced when agent called `list_dir("/home/tuna/tunacode/apps")` - a directory that doesn't exist. Agent crashed with `ToolExecutionError` instead of retrying.

## Root Cause

Error propagation chain:
1. `list_dir` raises `FileNotFoundError`
2. `@base_tool` decorator wraps it as `ToolExecutionError`
3. `tool_executor.py` has `ToolExecutionError` in `NON_RETRYABLE_ERRORS`
4. Non-retryable errors propagate immediately, halting the agent

First attempted fix: switch to `@file_tool` decorator. Failed because `@file_tool` expects required `filepath` positional arg, but `list_dir` has optional `directory="."`.

## Changes

- Import `ModelRetry` from `pydantic_ai.exceptions`
- Replace `raise FileNotFoundError(...)` with `raise ModelRetry(...)`
- Replace `raise NotADirectoryError(...)` with `raise ModelRetry(...)`
- Keep `@base_tool` decorator (not `@file_tool`)

## Behavioral Impact

- Agent no longer halts on bad directory paths
- LLM receives retry signal with error message, can self-correct
- No change to valid path behavior

## Related Cards

- [[glob-grep-error-strings]] - similar smell: return error strings instead of raising
