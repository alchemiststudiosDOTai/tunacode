# Task 01: Canonical Messaging Adoption

## Summary
Production message handling does not use the canonical message and part types even though they exist. This creates a split between the tested canonical model and the runtime model, increasing the chance of divergent behavior and inconsistent message access patterns.

## Context
Canonical types live in `src/tunacode/types/canonical.py` and the adapter functions live in `src/tunacode/utils/messaging/adapter.py`, with strong test coverage in `tests/unit/types/test_canonical.py` and `tests/unit/types/test_adapter.py`. Runtime paths still rely on legacy accessors such as `get_message_content()` in `src/tunacode/utils/messaging/message_utils.py`, called from `src/tunacode/core/state.py`, `src/tunacode/ui/app.py`, and `src/tunacode/ui/headless/output.py`.

## Key Findings
- Direct legacy accessor calls remain in `src/tunacode/core/state.py:28`, `src/tunacode/core/state.py:123`, `src/tunacode/ui/app.py:352`, `src/tunacode/ui/app.py:355`, `src/tunacode/ui/headless/output.py:7`, `src/tunacode/ui/headless/output.py:50`.
- Tool-call tracking logic is duplicated between the canonical adapter helpers in `src/tunacode/utils/messaging/adapter.py:261` and the resume sanitization flow in `src/tunacode/core/agents/resume/sanitize.py:171`.
- Resume sanitization remains highly polymorphic and large (630 lines), with custom tool-call ID collection and dangling-call detection in `src/tunacode/core/agents/resume/sanitize.py:116` through `src/tunacode/core/agents/resume/sanitize.py:220`.
- Core agent cleanup depends on the resume sanitization helpers in `src/tunacode/core/agents/main.py:365`.

## Next Steps
1. Replace legacy `get_message_content()` usage with adapter `get_content()` in the three production call sites listed above.
2. Draft a canonical-adapter based path for tool-call ID collection/dangling detection in resume sanitization, then reduce `src/tunacode/core/agents/resume/sanitize.py`.
3. Centralize tool-call tracking by routing cleanup in `src/tunacode/core/agents/main.py` through the canonical adapter helpers.

## Related Docs
- [PLAN.md](../../PLAN.md)
- [Architecture Refactor Status Research](../../memory-bank/research/2026-01-25_architecture-refactor-status.md)
