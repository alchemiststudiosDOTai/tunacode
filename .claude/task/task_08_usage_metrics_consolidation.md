# Task 08: Usage Metrics Consolidation

## Summary
Usage tracking relies on ad hoc dictionary structures and duplicates totals across multiple fields. This makes metric definitions inconsistent and complicates reporting.

## Context
`src/tunacode/core/state.py` stores `last_call_usage` and `session_total_usage` as dicts with repeated fields. Canonical `UsageMetrics` exists in `src/tunacode/types/canonical.py`, and `TokenUsage` and `CostBreakdown` exist in `src/tunacode/types/dataclasses.py`, but production usage remains untyped.

## Related Docs
- [PLAN.md](../../PLAN.md)
- [Architecture Refactor Status Research](../../memory-bank/research/2026-01-25_architecture-refactor-status.md)
