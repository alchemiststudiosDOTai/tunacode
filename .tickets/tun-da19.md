---
id: tun-da19
status: open
deps: []
links: []
created: 2026-02-01T03:24:47Z
type: task
priority: 1
assignee: tunahorse1
parent: tun-7f83
tags: [concurrency, tools, registry]
---
# Synchronize tool registry access

Add synchronization around tool registry mutation/access to prevent race conditions during parallel tool runs.

## Acceptance Criteria

Concurrent tool registration/lookup does not race; synchronization is explicit and documented; no new type errors.

