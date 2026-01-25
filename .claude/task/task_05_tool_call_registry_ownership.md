# Task 05: Tool Call Registry Ownership

## Summary
Tool call lifecycle data is tracked in three separate places, which creates a high risk of divergence and unclear ownership. The lack of a single source of truth makes auditing and reconciliation difficult.

## Context
`SessionState` holds `tool_calls` and `tool_call_args_by_id` in `src/tunacode/core/state.py`, while message parts also represent tool call history. `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py` and `src/tunacode/core/agents/resume/sanitize.py` both manipulate this data. `CanonicalToolCall` exists in `src/tunacode/types/canonical.py`, but a registry is not present.

## Related Docs
- [PLAN.md](../../PLAN.md)
- [Architecture Refactor Status Research](../../memory-bank/research/2026-01-25_architecture-refactor-status.md)
