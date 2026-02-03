---
title: Remove heuristic token counting from agent flow
link: remove-heuristic-token-counting
type: delta
path: src/tunacode/core/agents/main.py
depth: 0
seams: [S, M]
ontological_relations:
  - relates_to: [[usage-tracking]]
  - affects: [[agent-flow]]
  - affects: [[session-state]]
tags:
  - tokens
  - usage
  - performance
  - cleanup
created_at: 2026-02-02T16:59:25-06:00
updated_at: 2026-02-02T16:59:25-06:00
uuid: 3b4c0dae-f00e-4b01-bba3-2537fd150899
---

# Remove heuristic token counting from agent flow

## Summary

The agent run flow no longer recomputes token totals by iterating over message
history. This removes the slow heuristic `update_token_count` path in favor of
usage totals as the canonical source for token display.

## Context

- `SessionState.update_token_count()` and `adjust_token_count()` were used after
  message mutations (cleanup, abort handling, persistence).
- These methods depended on `estimate_messages_tokens`, which scales poorly with
  large histories and does not match provider usage totals.

## Changes

- Removed `update_token_count` calls from `core/agents/main.py` cleanup and
  persistence paths.
- Deleted `SessionState.update_token_count()` and `adjust_token_count()` along
  with the heuristic import in `core/state.py`.
- Removed `update_token_count` from `SessionStateProtocol`.

## Behavioral Impact

- Message cleanup no longer recalculates `conversation.total_tokens`.
- UI token display will rely on usage totals rather than heuristic counts.

## Related Cards

- [[usage-total-token-source]]
