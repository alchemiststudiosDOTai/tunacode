---
date: 2026-02-04
type: refactoring
scope: core/agents
impact: medium
---

# Main Agent Module Refactoring

## Summary

Refactored `src/tunacode/core/agents/main.py` from 641 lines to 389 lines (39% reduction) by extracting focused modules and removing dead code.

## Changes

### New Files Created

1. **`history_preparer.py`** - `HistoryPreparer` class
   - Encapsulates message history preparation logic
   - Handles pruning, cleanup, and sanitization
   - Single `prepare()` method returns ready-to-use history

2. **`request_logger.py`** - Logging utilities
   - `log_history_state()` - Logs message history for diagnostics
   - `log_sanitized_history_state()` - Logs sanitized history in debug mode
   - `log_run_handle_context_messages()` - Logs pydantic-ai context
   - `log_node_details()` - Logs node type information
   - `message_has_tool_calls()` - Helper for detecting tool calls

### Removed Dead Code

- `DotDict` class - Unused utility class
- `colors` variable - Never referenced
- `IterationManager` class - Trivially simple, inlined into `_handle_iteration_node()`

### Cleaned Up

- `EmptyResponseHandler.prompt_action()` - Replaced inline `StateProxy` class with `@dataclass StateView`
- Simplified counter tracking logic in `EmptyResponseHandler.track()`

## Rationale

The original `main.py` had accumulated multiple responsibilities:
- Request initialization
- Message history preparation (7+ methods)
- Logging (7+ methods)
- Agent iteration loop
- Node handling
- Abort cleanup

This violated single responsibility principle and made the file difficult to navigate.

## Architecture Compliance

All new modules follow layer dependency rules:
- `core` modules only import from `tools`, `utils`, `types`, and `infrastructure`
- No imports from `ui` layer

Verified by passing `tests/architecture/test_layer_dependencies.py`.

## Updated Documentation

- `docs/codebase-map/modules/core-agents.md` - Updated exports and component list
- `docs/architecture/agent-loop.md` - Updated line references and file list
