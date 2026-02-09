---
title: "Phase 2: Wrap tools as tinyAgent AgentTool.execute (remove ModelRetry bridge)"
link: "tun-1ad5-wrap-tools-as-tinyagent-agenttool"
type: "delta"
path:
  - "src/tunacode/tools/decorators.py"
  - "src/tunacode/exceptions.py"
  - "src/tunacode/core/agents/agent_components/tool_executor.py"
  - "tests/unit/tools/test_tool_decorators.py"
  - "tests/integration/tools/test_glob_grep_path_validation.py"
  - "tests/integration/tools/test_tool_retry.py"
  - "tests/unit/core/test_text_match.py"
  - "tests/unit/tools/test_tinyagent_tool_adapter.py"
depth: 0
seams: [A, M]
ontological_relations:
  - relates_to: "[[tun-1658-tinyagent-migration]]"
  - affects: "[[tunacode-tools]]"
  - affects: "[[tool-retry-semantics]]"
tags:
  - migration
  - tinyagent
  - tools
  - retry
created_at: 2026-02-07T15:48:00-06:00
updated_at: 2026-02-07T15:48:00-06:00
uuid: 1b451b9c-8f72-4f1e-9dfe-fb73bb8d053d
---

## Summary

Removed the pydantic-ai `ModelRetry` bridge from the tool layer and added a tinyAgent adapter that exposes TunaCode tools as `tinyagent.AgentTool` instances with the fixed `execute(tool_call_id, args, signal, on_update)` signature.

## Changes

- `src/tunacode/tools/decorators.py`
  - `ToolRetryError` now passes through (no conversion to `pydantic_ai.ModelRetry`).
  - `file_tool` converts `FileNotFoundError` to `ToolRetryError` instead of `ModelRetry`.
  - Added `to_tinyagent_tool()` to emit `tinyagent.AgentTool` objects.
  - Added best-effort OpenAI-function JSON schema generation from tool signatures.

- `src/tunacode/core/agents/agent_components/tool_executor.py`
  - `ToolRetryError` is now treated as non-retryable by the automatic tool retry loop.

- Tests
  - Updated decorator/path-validation/retry tests to assert `ToolRetryError` instead of `ModelRetry`.
  - Added unit tests for `to_tinyagent_tool()`.

## Behavioral Impact

- Tool retry hints are now represented as `ToolRetryError` all the way up to the agent loop.
- Tools can be registered into tinyAgent without additional per-tool wrappers.

## Related Cards

- [[tun-1658-tinyagent-migration]]
