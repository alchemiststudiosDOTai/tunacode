---
id: t-ea8a
status: closed
deps: []
links: [t-6162]
created: 2026-01-26T07:13:30Z
type: task
priority: 1
tags: [architecture, ui, core, indexing]
---
# Evict indexing logic from UI layer

The UI currently directly imports and manages the CodeIndex background task in src/tunacode/ui/startup.py and src/tunacode/ui/app.py. This violates the 'Dependency Direction' rule from AGENTS.md where the UI should only know about the Core.

## Design

1. Move the indexing orchestration logic from src/tunacode/ui/startup.py to a Core service (e.g., StateManager or a new CodebaseService).\n2. Remove 'from tunacode.indexing' imports from all files in src/tunacode/ui/.\n3. The UI should trigger indexing through the Core and observe state changes rather than passing a direct reference to UI widgets like RichLog into indexing functions.

## Acceptance Criteria

1. 'grep -r tunacode.indexing src/tunacode/ui' returns no results.\n2. layers.dot shows 0 links for ui -> indexing.\n3. Background indexing still starts on app launch and provides visual feedback to the user via Core state updates.


## Notes

**2026-01-26T07:34:15Z**

Closed in favor of Epic t-6162 which has a more detailed breakdown.
