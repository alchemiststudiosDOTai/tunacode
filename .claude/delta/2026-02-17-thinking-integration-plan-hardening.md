---
title: Thinking integration plan hardening for junior handoff
type: delta
link: thinking-integration-plan-hardening
path: memory-bank/plan/2026-02-17_thinking-content-integration.md
depth: 0
seams: [M]
ontological_relations:
  - affects: [[planning]]
  - affects: [[ui]]
  - affects: [[core-agents]]
tags:
  - plan
  - thinking
  - tinyagent
  - handoff
created_at: 2026-02-17T13:45:00-06:00
updated_at: 2026-02-17T13:45:00-06:00
uuid: 5b62db69-9c88-4fc0-8f55-1e5c44295f3b
---

# Thinking integration plan hardening for junior handoff

## Summary

Refined the thinking-content integration plan to remove execution ambiguity and close known blindspots so a junior engineer can implement directly from the document.

## What changed

- Replaced ambiguous task language with explicit file-level edits and acceptance gates.
- Corrected callback typing to use `StreamingCallback` (existing alias).
- Added missing `process_request(..., thinking_callback=...)` plumbing step.
- Fixed command architecture guidance: `/thoughts` is implemented in `ui/commands`, not in `app.py` inline parsing.
- Added preflight validation for tinyagent thinking stream events.
- Added mandatory neXTSTEP UI skill precondition for UI edits.
- Added explicit text-only extraction requirement for final assistant panel to keep reasoning separate.
- Added concrete test files and ordered verification gates.
