---
title: Canonical token total uses usage totals
link: usage-total-token-source
type: doc
path: src/tunacode/core/agents/agent_components/orchestrator/usage_tracker.py
depth: 0
seams: [S, M]
ontological_relations:
  - relates_to: [[usage-tracking]]
  - affects: [[resource-bar]]
  - affects: [[session-usage-metrics]]
tags:
  - tokens
  - usage
  - ui
created_at: 2026-02-02T16:59:25-06:00
updated_at: 2026-02-02T16:59:25-06:00
uuid: d78e6d77-0ca6-4050-9a14-8da069b2325a
---

# Canonical token total uses usage totals

## Summary

The canonical token total for UI display is the accumulated pydantic-ai usage totals
(prompt + completion) from `usage.session_total_usage`, not heuristic message counting.
This aligns the UI with billed API usage and avoids slow per-message estimation.

## Context

- The UI previously used `conversation.total_tokens`, which is computed by
  `estimate_messages_tokens` over the full message list.
- Pydantic-ai always exposes a `RequestUsage`, but providers may return all zeros when
  usage is unavailable.
- `RequestUsage` does not expose cached token counts, so cache usage cannot be reported.

## Root Cause

Heuristic token counting is both slow on large histories and inconsistent with actual
API usage totals, causing UI token numbers to drift from provider-reported usage.

## Changes

- Define the canonical token total as `usage.session_total_usage.total_tokens`
  (prompt + completion).
- Treat zero-usage responses as valid zeros; do not fall back to heuristics.
- Keep cached tokens at zero because `RequestUsage` does not supply them.
- Retain `conversation.total_tokens` only for context-window sizing, not UI usage totals.

## Behavioral Impact

- The UI token display reflects API usage totals and may remain at 0 when providers omit
  usage data.
- Cached token counts are not displayed until providers supply a value.
- Context-window size is no longer conflated with usage totals.

## Related Cards

- [[usage-tracking]]
- [[resource-bar]]
