---
id: t-06af
status: closed
deps: [t-9fa8]
links: []
created: 2026-01-26T07:33:12Z
type: task
priority: 2
parent: t-6162
tags: [ui, cleanup]
---
# Delete ui/startup.py and verify cleanup

Remove the now-obsolete ui/startup.py file and verify that no indexing imports remain in the UI layer.

## Acceptance Criteria

ui/startup.py is deleted. grep -r tunacode.indexing src/tunacode/ui returns empty.

