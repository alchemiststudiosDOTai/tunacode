---
id: tun-3df0
status: closed
deps: [tun-2483]
links: []
created: 2026-01-27T18:00:24Z
type: task
priority: 1
tags: [issue-313, phase-3, facade]
---
# Route messaging through tools/messaging/

Create tools/messaging/__init__.py facade that re-exports from utils/messaging/. Update 6 core files to import from tools.messaging instead of utils.messaging. Eliminates 10 core->utils imports while respecting layer architecture (core -> tools -> utils).

## Acceptance Criteria

tools/messaging/__init__.py exists and re-exports; core imports from tools.messaging; utils/messaging/ remains in place; tests pass

