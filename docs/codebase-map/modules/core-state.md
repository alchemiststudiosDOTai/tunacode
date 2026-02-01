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
- **_message_token_cache** - Cached per-message token lengths to avoid rescans
- **task** - Typed todo tracking and original query
- **runtime** - Iteration counters, tool call registry, request metadata, streaming flags
- **usage** - Per-call and cumulative usage metrics
- **user_config** - User settings and preferences
- **agents** - Cached pydantic-ai Agent instances
- **agent_versions** - Version tracking for cache invalidation
- **current_model** - Active model name
- **_debug_events** - Capped list of streaming debug events (max 200)
- **_debug_raw_stream_accum** - Capped raw stream accumulator (max 20K chars)

### StateManager
Singleton class with global instance access:
- **session** - Retrieve SessionState instance
- **conversation/task/runtime/usage** - Typed sub-state accessors
- **update_token_count()** - Recompute total tokens using cached per-message lengths
- **save_session()** - Persist session to disk
- **load_session()** - Restore session from disk

## Persistence Contract

- Messages must be dicts or pydantic-ai `ModelMessage` instances; serialization
  raises on unsupported types to prevent silent data loss.
- `save_session()` stamps `last_modified` and writes JSON to the session store.

### Async I/O

Session persistence uses **async file I/O** via `asyncio.to_thread()` to avoid blocking the event loop during disk operations:

- **`save_session()`** - Serializes session data, then writes via `_write_session_file()` in a thread pool
- **`load_session()`** - Reads via `_read_session_data()` in a thread pool, then deserializes

This prevents UI stalls during auto-save and session restoration, especially on slower storage.

## State Transitions

```
Initial → Configured → Active → Paused → Saved
```

## Integration Points

- **core/agents/** - Agent creation and caching
- **ui/** - Real-time state updates in TUI
- **configuration/** - User config loading

## Seams (M)

**Modification Points:**
- Add new SessionState fields for extended session tracking
- Customize persistence format (currently JSON)
- Add state validation logic
- Implement state migration for version upgrades
