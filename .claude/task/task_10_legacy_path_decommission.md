# Task 10: Legacy Path Decommission

## Summary
Legacy message access patterns and polymorphic flows remain active, keeping the system anchored to older behavior even as canonical types exist. This preserves divergence between modern and legacy paths.

## Context
`src/tunacode/utils/messaging/message_utils.py` provides `get_message_content()`, which is still called from `src/tunacode/core/state.py`, `src/tunacode/ui/app.py`, and `src/tunacode/ui/headless/output.py`. Polymorphic sanitization in `src/tunacode/core/agents/resume/sanitize.py` also remains part of the runtime flow.

## Related Docs
- [PLAN.md](../../PLAN.md)
- [Architecture Refactor Status Research](../../memory-bank/research/2026-01-25_architecture-refactor-status.md)
