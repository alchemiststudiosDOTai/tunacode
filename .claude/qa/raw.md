[2026-01-15] [bug] message history missed tool-return when request ended early; fix by persisting agent_run.all_messages and keeping system notices out of history.
[2026-01-16] [bug] tool panels rendered to the RichLog content region width; fix by setting explicit panel frame width from max_line_width plus TOOL_PANEL_HORIZONTAL_INSET.
[2026-01-21] [bug] dangling tool calls could persist mid-history and stall the API; fix by scanning all messages for unmatched tool calls and removing them.
[2026-01-21] [bug] cleanup attempted to set read-only ModelResponse.tool_calls; fix by only mutating dict-backed tool_calls.
[2026-01-21] [bug] model request streaming could hang before stream open; add stream watchdog and log outgoing request parts for debug.
[2026-01-26] [bug] ReAct removal left forced_calls/guidance access in agents/main.py, triggering AttributeError on ReActState.
2026-01-25 [smell] tools importing core limits forced allowlist; moved limits to utils to preserve dependency direction.
