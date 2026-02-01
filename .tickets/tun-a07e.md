---
id: tun-a07e
status: closed
deps: []
links: []
created: 2026-02-01T02:38:25Z
type: task
priority: 2
assignee: tunahorse1
parent: tun-0154
tags: [perf, core, streaming]
---
# Cap streaming debug accumulators

Bound debug stream accumulators to prevent unbounded growth during long responses.

## Acceptance Criteria

Debug accumulators in streaming are size-bounded with symbolic constants; newest data retained; no unbounded concatenation in loops.

