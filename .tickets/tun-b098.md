---
id: tun-b098
status: open
deps: []
links: []
created: 2026-01-27T18:07:58Z
type: task
priority: 1
tags: [issue-313, phase-1, inline]
---
# Phase 1: Inline tiny utilities (formatting, DotDict)

Inline utils/formatting.py into core/formatting.py and DotDict class into core/agents/main.py. Delete original utils files. Eliminates 2 core->utils imports.

## References
- Plan: memory-bank/plan/2026-01-27_17-59-28_issue-313-core-utils-layer-violation.md (Task 1)
- Architecture: docs/architecture/NEW_layers.html (Phase 1)
- Issue: https://github.com/alchemiststudiosDOTai/tunacode/issues/313

## Files
- Inline: utils/formatting.py (6 lines) -> core/formatting.py
- Inline: utils/ui/helpers.py DotDict (14 lines) -> core/agents/main.py
- Delete: utils/formatting.py, utils/ui/helpers.py

## Acceptance Criteria

core/formatting.py contains truncate_diagnostic_message body; core/agents/main.py contains DotDict class; utils files deleted; tests pass

