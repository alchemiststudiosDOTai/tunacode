---
id: tun-b9c8
status: open
deps: [tun-b098]
links: []
created: 2026-01-27T18:08:05Z
type: task
priority: 1
tags: [issue-313, phase-2, move]
---
# Phase 2: Move config modules to configuration/

Move 4 utils modules to foundation layer (configuration/).

## References
- Plan: memory-bank/plan/2026-01-27_17-59-28_issue-313-core-utils-layer-violation.md (Task 2)
- Architecture: docs/architecture/NEW_layers.html (Phase 2)
- Issue: https://github.com/alchemiststudiosDOTai/tunacode/issues/313

## Moves
- utils/config/user_configuration.py -> configuration/user_config.py
- utils/limits.py -> configuration/limits.py
- utils/system/paths.py -> configuration/paths.py
- utils/system/ignore_patterns.py -> configuration/ignore_patterns.py

## Update Imports In
- core/agent_config.py, core/user_configuration.py, core/state.py
- core/system_paths.py, core/file_filter.py

## Acceptance Criteria

All 4 modules in configuration/; core imports from configuration/; old utils deleted; tests pass

