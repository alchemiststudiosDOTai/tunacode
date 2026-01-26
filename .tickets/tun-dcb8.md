---
id: tun-dcb8
status: closed
deps: []
links: []
created: 2026-01-26T16:54:41Z
type: task
priority: 2
tags: [ui, dependency-direction, gate-2]
---
# Move IGNORE_PATTERNS_COUNT to tool result

Remove IGNORE_PATTERNS_COUNT import from ui/renderers/tools/list_dir.py by including the count in the tool result dict instead of importing from tools layer.

## Acceptance Criteria

No 'from tunacode.tools' imports in ui/renderers/tools/list_dir.py. Ignore count still displays correctly.


## Notes

**2026-01-26T18:06:32Z**

Completed in commit 1d0647c7
