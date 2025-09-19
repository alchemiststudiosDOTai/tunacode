# React Tool Session Snapshot

- Added `ReactTool` to capture ReAct scratchpad interactions via `react` tool name.
- Extended `StateManager` with `react_scratchpad` helpers for think/observe timeline management.
- Registered tool as read-only in agent configuration; kept prompt and schema minimal.
- Covered behavior with `tests/unit/test_react_tool.py` capturing think→observe sequence.
