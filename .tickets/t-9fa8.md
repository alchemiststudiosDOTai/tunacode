---
id: t-9fa8
status: closed
deps: [t-6f0e]
links: []
created: 2026-01-26T07:33:09Z
type: task
priority: 2
parent: t-6162
tags: [ui, refactor]
---
# Refactor ui/app.py to use IndexingService

Update TunaCodeApp to use state_manager.indexing_service instead of calling ui/startup.py directly. Implement the status callback to write to RichLog.

## Acceptance Criteria

Indexing still works and provides visual feedback via RichLog.

