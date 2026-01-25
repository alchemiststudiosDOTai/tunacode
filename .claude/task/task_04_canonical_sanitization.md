# Task 04: Canonical Sanitization

## Summary

Message sanitization is currently polymorphic, complex, and spread across multiple code paths. This increases the risk of inconsistent cleanup rules and tool call linkage issues.

## Context

`src/tunacode/core/agents/resume/sanitize.py` is a large file with custom accessors for dict and object messages, including separate branches for tool call collection and dangling tool call removal. The refactor plan references a canonical sanitization flow, but it is not present.

We should NOT refactor but rebuild cleanly

## Related Docs

- [PLAN.md](../../PLAN.md)
- [Architecture Refactor Status Research](../../memory-bank/research/2026-01-25_architecture-refactor-status.md)
