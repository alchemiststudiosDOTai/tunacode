---
title: Core State Management
path: src/tunacode/core/state.py
type: file
depth: 1
description: Central session state management and configuration tracking
exports: [StateManager, SessionState]
seams: [M]
---

# Core State Management

## Purpose
Central singleton managing all session data including conversation history, user configuration, agent cache, and token tracking.

## Key Classes

### SessionState
Dataclass container for all session data with decomposed sub-structures:
- **conversation** - Messages, thoughts, token totals, context tracking
- **react** - Scratchpad timeline, forced call counter, guidance entries
- **task** - Typed todo tracking and original query
- **runtime** - Iteration counters, tool call registry, request metadata, streaming flags
- **usage** - Per-call and cumulative usage metrics
- **user_config** - User settings and preferences
- **agents** - Cached pydantic-ai Agent instances
- **agent_versions** - Version tracking for cache invalidation
- **current_model** - Active model name
- **tool_ignore** - Tools approved for auto-execution
- **tool_progress_callback** - UI callback for tool updates

### StateManager
Singleton class with global instance access:
- **session** - Retrieve SessionState instance
- **conversation/react/task/runtime/usage** - Typed sub-state accessors
- **update_token_count()** - Track token usage
- **save_session()** - Persist session to disk
- **load_session()** - Restore session from disk

## Persistence Contract

- Messages must be dicts or pydantic-ai `ModelMessage` instances; serialization
  raises on unsupported types to prevent silent data loss.
- `save_session()` stamps `last_modified` and writes JSON to the session store.

## State Transitions

```
Initial → Configured → Active → Paused → Saved
```

## Integration Points

- **core/agents/** - Agent creation and caching
- **ui/** - Real-time state updates in TUI
- **configuration/** - User config loading
- **tools/** - Tool authorization state

## Seams (M)

**Modification Points:**
- Add new SessionState fields for extended session tracking
- Customize persistence format (currently JSON)
- Add state validation logic
- Implement state migration for version upgrades
