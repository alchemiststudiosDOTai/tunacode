---
title: Resource bar shows usage-total tokens
link: resource-bar-usage-totals
type: delta
path: src/tunacode/ui/app.py
depth: 0
seams: [S, M]
ontological_relations:
  - relates_to: [[resource-bar]]
  - affects: [[usage-tracking]]
  - affects: [[ui-tokens]]
tags:
  - ui
  - tokens
  - usage
created_at: 2026-02-02T17:05:00-06:00
updated_at: 2026-02-02T17:05:00-06:00
uuid: d674d5bd-6143-48dc-a434-8c6b9cce387b
---

# Resource bar shows usage-total tokens

## Summary

The resource bar now reads token totals from accumulated usage metrics rather than
heuristic message counts, keeping the UI aligned with provider-reported usage.

## Context

`TextualReplApp._update_resource_bar()` previously used `conversation.total_tokens`,
which is derived from per-message estimation.

## Changes

- Switched resource bar token source to `session.usage.session_total_usage.total_tokens`.

## Behavioral Impact

- Token display reflects API usage totals after each request.
- Context-window counts are no longer used for the UI token indicator.

## Related Cards

- [[usage-total-token-source]]
- [[remove-heuristic-token-counting]]
