---
id: tun-b941
status: closed
deps: [tun-3df0]
links: []
created: 2026-01-27T18:00:24Z
type: task
priority: 2
tags: [issue-313, phase-4, move]
---
# Move parsing to tools/ and file_filter to infrastructure/

Move utils/parsing/ -> tools/parsing/. Move utils/ui/file_filter.py -> infrastructure/file_filter.py. Create infrastructure/__init__.py. Update tool_dispatcher.py and core/file_filter.py. Eliminates 3 core->utils imports.

## Acceptance Criteria

tools/parsing/ exists; infrastructure/file_filter.py exists; core imports from tools.parsing and infrastructure; tests pass

