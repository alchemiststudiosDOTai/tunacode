# Task 07: Todo State Alignment

## Summary
Todo items are represented as generic dictionaries with no explicit lifecycle semantics, creating inconsistent task status tracking across the session lifecycle.

## Context
`src/tunacode/core/state.py` stores todos as `list[dict[str, Any]]`. Typed `TodoItem` and `TodoStatus` are available in `src/tunacode/types/canonical.py` but are not referenced by runtime state.

## Related Docs
- [PLAN.md](../../PLAN.md)
- [Architecture Refactor Status Research](../../memory-bank/research/2026-01-25_architecture-refactor-status.md)
