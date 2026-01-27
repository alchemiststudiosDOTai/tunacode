---
id: tun-e6ad
status: closed
deps: [tun-b941]
links: []
created: 2026-01-27T18:00:25Z
type: task
priority: 2
tags: [issue-313, phase-5, cleanup]
---
# Final cleanup and verification

Delete empty utils/ subdirectories. Verify zero core->utils violations with grep. Run full test suite. Update DEPENDENCY_MAP.md if needed.

## Acceptance Criteria

grep -r 'from tunacode.utils' src/tunacode/core/ returns 0 results; all tests pass; ruff check passes

