# React Tool Session Snapshot

- `ReactTool` captures ReAct scratchpad interactions while the agent now auto-invokes it every two iterations (up to five snapshots) via `_maybe_force_react_snapshot`, injecting each summary back into the conversation.
- `SessionState` tracks both the scratchpad timeline and a `react_forced_calls` ceiling so forced usage stays bounded per request.
- React is no longer registered as a selectable tool; documentation updated to reflect the forced snapshot workflow.
- `tests/unit/test_react_tool.py` covers both manual think/observe usage and the periodic auto snapshot helper.
