---
id: tun-ac8c
status: closed
deps: []
links: []
created: 2026-01-27T18:00:24Z
type: task
priority: 1
tags: [issue-313, phase-1, inline]
---
# Inline tiny utilities (formatting, DotDict) into core

Inline utils/formatting.py into core/formatting.py and DotDict class into core/agents/main.py. Delete the original utils files. Eliminates 2 core->utils imports.

## Acceptance Criteria

core/formatting.py contains truncate_diagnostic_message function body; core/agents/main.py contains DotDict class; utils/formatting.py and utils/ui/helpers.py deleted; tests pass

