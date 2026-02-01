---
id: tun-fb61
status: closed
deps: []
links: []
created: 2026-02-01T02:38:30Z
type: task
priority: 2
assignee: tunahorse1
parent: tun-0154
tags: [perf, core, streaming]
---
# Short-circuit streaming debug logging

Avoid debug reflection/logging work when debug mode is disabled.

## Acceptance Criteria

Hot-path streaming loop exits debug logic early when debug_mode is False; no debug reflection/logging executed when disabled.

