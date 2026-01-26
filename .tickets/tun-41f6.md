---
id: tun-41f6
status: closed
deps: []
links: []
created: 2026-01-26T16:54:42Z
type: task
priority: 2
tags: [ui, dependency-direction, gate-2]
---
# Move truncate_diagnostic_message to utils

Move truncate_diagnostic_message() from lsp/diagnostics.py to utils/formatting.py. Both LSP and UI can then import from utils (valid direction).

## Acceptance Criteria

No 'from tunacode.lsp' imports in ui/renderers/tools/diagnostics.py. Function exists in utils/formatting.py.

