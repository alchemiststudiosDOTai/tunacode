---
id: tun-a3d5
status: open
deps: [tun-8812]
links: []
created: 2026-01-27T18:08:21Z
type: task
priority: 2
tags: [issue-313, phase-4, move]
---
# Phase 4: Move parsing to tools/ and file_filter to infrastructure/

Move tool-specific parsing to Layer 2, file_filter to infrastructure.

## References
- Plan: memory-bank/plan/2026-01-27_17-59-28_issue-313-core-utils-layer-violation.md (Task 4)
- Architecture: docs/architecture/NEW_layers.html (Phase 4 & 5)
- Issue: https://github.com/alchemiststudiosDOTai/tunacode/issues/313

## Moves
- utils/parsing/ -> tools/parsing/
- utils/ui/file_filter.py -> infrastructure/file_filter.py

## Create
- infrastructure/__init__.py

## Update Imports In
- core/agents/.../tool_dispatcher.py -> tools.parsing
- core/file_filter.py -> infrastructure.file_filter

## Acceptance Criteria

tools/parsing/ exists; infrastructure/file_filter.py exists; core imports correct; tests pass

