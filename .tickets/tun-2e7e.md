---
id: tun-2e7e
status: in_progress
deps: []
links: []
created: 2026-02-01T03:24:45Z
type: task
priority: 1
assignee: tunahorse1
parent: tun-7f83
tags: [performance, state, token-counter]
---
# Add token count caching

Cache token counts to avoid O(n) rescans on each message update. Scope: state.py and token_counter integration.

## Acceptance Criteria

Token count is recomputed only when message content changes; cached values are reused on subsequent updates; no new type errors.

