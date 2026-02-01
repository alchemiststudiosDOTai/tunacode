---
id: tun-8168
status: closed
deps: []
links: []
created: 2026-02-01T02:38:21Z
type: task
priority: 1
assignee: tunahorse1
parent: tun-0154
tags: [perf, core, state]
---
# Async session persistence I/O

Move session save/load file I/O off the event loop using asyncio.to_thread (or equivalent) and update call sites/protocols to await as needed.

## Acceptance Criteria

save_session/load_session no longer call blocking open/json in async context; callers updated to await; type checks pass; behavior unchanged except non-blocking I/O.

