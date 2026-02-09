---
title: Remove legacy pydantic-ai orchestrator/tool-dispatcher
link: remove-legacy-orchestrator-tool-dispatcher
type: delta
path: src/tunacode/core/agents
depth: 2
seams: [A, M]
ontological_relations:
  - relates_to: [[tinyagent-migration]]
  - affects: [[core-agents-main-loop]]
  - affects: [[agent-components-package]]
tags:
  - migration
  - tinyagent
  - cleanup
created_at: 2026-02-07T22:14:36.946737+00:00
updated_at: 2026-02-07T22:14:36.946737+00:00
uuid: 01861b97-0dfa-40b9-8497-8fc650e46bd2
---

## Summary

Removed the now-dead node-based pydantic-ai orchestrator/tool-dispatcher stack after switching the request loop to consume tinyagent events directly. This reduces complexity and prevents accidental re-introduction of the legacy execution path.

## Changes

- Deleted `src/tunacode/core/agents/agent_components/orchestrator/` (tool dispatcher, usage tracker, node processor).
- Simplified exports:
  - `src/tunacode/core/agents/agent_components/__init__.py`
  - `src/tunacode/core/agents/__init__.py`
- Removed legacy tests that only validated the deleted orchestrator behavior:
  - `tests/integration/tools/test_tool_dispatcher_coverage.py`
  - `tests/integration/core/test_tool_call_lifecycle.py`
  - `tests/unit/core/test_usage_tracker.py`
- Refactored `RequestOrchestrator._run_stream()` into small event-specific handlers to satisfy Ruff complexity gates.

## Behavioral Impact

- Tool execution and streaming are now exclusively driven by tinyagent event handling.
- No backward-compatibility is provided for orchestrator-specific internals/tests.

## Related Cards

- [[tinyagent-migration]]
