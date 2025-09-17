# Main Agent Refactor Investigation Notes

Date: 2025-09-17
Branch: `main-agent-refactor`

## Observed Issues During Refactor Spike
- Import surface regression: `tunacode.core.agents.main` no longer exposed `get_or_create_agent`, yet CLI modules (`cli/repl.py`, debug/system commands) still imported it from there, causing `ImportError` at startup.
- Additional helpers (`patch_tool_messages`, `extract_and_execute_tool_calls`) were moved into `agent_components` without updating their callers, producing further `ImportError`s.
- Public API drift: downstream code expected to import from `tunacode.core.agents.main`, while the refactor assumed consumers would shift to `agent_components`; the repo lacks a consolidated, stable entry point.
- Runtime mismatch uncovered: after import fixes, `process_request` signature changes in the CLI wrapper masked the real agent entry point (`cli.repl.process_request`) and introduced incompatible call patterns (unexpected `tool_callback` keyword when invoking the agent-level function).

## Recommended Next Steps
1. Define `tunacode.core.agents` package exports as the supported public API and refactor consumers to import from there instead of `.main`.
2. Reconcile naming overlap between the CLI helper `process_request` and the agent coroutine; consider renaming or explicitly re-exporting to avoid shadowing and argument mismatches.
3. Introduce characterization tests around CLI startup to catch broken imports early during refactors.

These notes capture the blockers encountered before rolling back to the snapshot commit `d88c959`.
