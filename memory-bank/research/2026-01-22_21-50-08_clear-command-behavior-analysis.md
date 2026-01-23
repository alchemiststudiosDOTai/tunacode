---
title: "/clear Command Behavior Analysis"
link: "clear-command-behavior-analysis"
type: "research"
depth: 0
seams: [E]
ontological_relations:
  - relates_to: [[session-management]]
  - affects: [[ui-commands]]
  - fixes: [[clear-command-misleading-behavior]]
tags:
  - clear-command
  - session-state
  - ux
  - state-management
created_at: "2026-01-22T21:50:08Z"
updated_at: "2026-01-22T23:15:00Z"
git_branch: "master"
git_commit: "6b9ddf4adcd12353b77522850798ee6e4bd679ef"
owner: "claude-code-agent"
phase: "implementation-ready"
uuid: "01935ef8-9b5c-7a00-9e7c-d9e1a4c8e3e1"
---

# Research – /clear Command Behavior Analysis

**Date:** 2026-01-22
**Owner:** claude-code-agent
**Phase:** Research
**Git Branch:** master
**Git Commit:** 6b9ddf4adcd12353b77522850798ee6e4bd679ef

## Goal

Analyze the `/clear` command implementation to understand:
1. What state is actually cleared vs. what users expect to be cleared
2. What constitutes a "fresh start" within the same session
3. Which fields should be cleared vs. preserved
4. Existing helper methods that can be leveraged

## Executive Summary

**Key Finding:** The `/clear` command is **incomplete**. While it correctly clears conversation messages and UI display, it only touches 2 of 42+ SessionState fields. Users expect `/clear` to reset accumulated conversation state (thoughts, tool calls, todos, counters) while preserving their configuration (model, yolo, debug_mode) and session identity.

**Current behavior:**
- Clears: `messages`, `total_tokens`, UI display
- Preserves: Everything else (41 fields including runtime state, counters, todos, thoughts)
- **PROBLEM:** Next auto-save overwrites disk with empty messages → conversation lost on `/resume`

**Expected behavior for "fresh start":**
- Clear: Agent working state (thoughts, tool calls, todos, counters, ReAct scratchpad)
- Preserve: Conversation messages (for `/resume`), user configuration, session identity
- **Goal:** Clean slate for agent, but conversation history survives for later review

## Current Implementation

**Location:** `src/tunacode/ui/commands/__init__.py:71-80`

```python
class ClearCommand(Command):
    name = "clear"
    description = "Clear conversation history"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        app.rich_log.clear()                              # UI display
        app.state_manager.session.messages = []           # Messages
        app.state_manager.session.total_tokens = 0        # Token count
        app._update_resource_bar()
        app.notify("Cleared conversation history")
```

**What is cleared:**
| Field | Type | Purpose |
|-------|------|---------|
| `rich_log` | UI component | Visual conversation display |
| `messages` | `MessageHistory` | Conversation message history |
| `total_tokens` | `int` | Estimated token count |

## User-Facing Documentation

| Location | Text |
|----------|------|
| `src/tunacode/ui/welcome.py:44` | `/clear      - Clear conversation` |
| `README.md:92` | `/clear   \| Clear conversation history` |
| `/help` command output | `Clear conversation history` |
| `docs/codebase-map/modules/ui-overview.md:123` | `Clear conversation history` |

All documentation consistently states "Clear conversation history" which is **technically accurate but potentially misleading**—users may expect a complete reset.

## SessionState Fields Analysis (42 Total Fields)

### Category 1: Currently Cleared (2 fields) - **WRONG BEHAVIOR**

| Field | Line | Purpose | Current Status | Correct Behavior |
|-------|------|---------|----------------|------------------|
| `messages` | 44 | Conversation message history | ✓ Cleared | ✗ Should PRESERVE |
| `total_tokens` | 87 | Estimated token count | ✓ Cleared | ✓ Can clear (recalculated on resume) |

### Category 2: SHOULD BE Cleared - Agent Working State (21 fields) ✗

These fields are agent working memory that should be reset for a "fresh start" while preserving the conversation:

| Field | Line | Purpose | Why Clear |
|-------|------|---------|-----------|
| `thoughts` | 45 | Agent thinking trace | Conversation-specific reasoning |
| `tool_calls` | 78 | History of tool invocations | Past execution history |
| `tool_call_args_by_id` | 79 | Cached tool arguments | In-progress call cache |
| `react_scratchpad` | 69 | ReAct tooling timeline | Accumulated observations |
| `react_forced_calls` | 70 | Counter for forced ReAct snapshots | Session counter |
| `react_guidance` | 71 | Guidance messages for ReAct | Context-specific guidance |
| `todos` | 73 | Session todo list | Task-specific todos |
| `files_in_context` | 77 | Set of files in context | Conversation-specific files |
| `iteration_count` | 80 | Total iterations | Session counter |
| `current_iteration` | 81 | Current request iteration | Request counter |
| `consecutive_empty_responses` | 118 | Empty response counter | Error detection state |
| `batch_counter` | 119 | Batch operation counter | Session counter |
| `_debug_events` | 112 | Debug instrumentation events | Runtime debug data |
| `_debug_raw_stream_accum` | 113 | Raw stream accumulator | Streaming debug buffer |
| `request_id` | 115 | Current request lifecycle ID | Request-specific ID |
| `original_query` | 116 | Original user query | Request-specific query |
| `operation_cancelled` | 75 | Operation cancellation flag | Runtime flag |
| `last_call_usage` | 90-96 | Last API call token/cost | Last call metrics |
| `session_total_usage` | 97-103 | Cumulative session usage | **Debatable** - session metrics |
| **Recursive execution state** (5 fields): |
| `current_recursion_depth` | 104 | Current nesting level | Execution state |
| `parent_task_id` | 106 | Parent task identifier | Execution state |
| `task_hierarchy` | 107 | Task nesting structure | Execution state |
| `iteration_budgets` | 108 | Per-task iteration limits | Execution state |
| `recursive_context_stack` | 109 | Execution context stack | Execution state |

### Category 3: MUST PRESERVE - Conversation History (2 fields) ✓

**CRITICAL:** These must survive `/clear` so conversation can be resumed later:

| Field | Line | Purpose | Why Preserve |
|-------|------|---------|--------------|
| `messages` | 44 | Conversation message history | **Session persistence - user needs /resume** |
| `total_tokens` | 87 | Estimated token count | Recalculated on load, but can preserve |

### Category 4: MUST PRESERVE - User Configuration (8 fields) ✓

User preferences that should survive /clear:

| Field | Line | Purpose | Why Preserve |
|-------|------|---------|--------------|
| `user_config` | 39 | User configuration | Contains API keys, settings |
| `current_model` | 47 | Currently selected model | User choice |
| `tool_ignore` | 49 | Tools to ignore/auto-approve | User preferences |
| `yolo` | 51 | Auto-confirm mode toggle | User preference |
| `debug_mode` | 52 | Debug logging toggle | User preference |
| `plan_mode` | 53 | Plan mode toggle | User preference |
| `show_thoughts` | 58 | Show agent thoughts toggle | User preference |
| `max_tokens` | 88 | Model context window limit | Configuration constant |

### Category 5: MUST PRESERVE - Session Identity (5 fields) ✓

These define the session and cannot be cleared without creating a new session:

| Field | Line | Purpose | Why Preserve |
|-------|------|---------|--------------|
| `session_id` | 59 | Unique session identifier | Session identity |
| `project_id` | 64 | Project identifier | Session storage |
| `created_at` | 65 | Session creation timestamp | Session metadata |
| `last_modified` | 66 | Last save timestamp | Session metadata |
| `working_directory` | 67 | CWD when session started | Session context |

### Category 6: PRESERVE - Runtime References (11 fields) ✓

System objects that should not be touched:

| Field | Line | Purpose | Why Preserve |
|-------|------|---------|--------------|
| `agents` | 40 | Agent instances cache | System objects |
| `agent_versions` | 42 | Agent version tracking | Cache metadata |
| `spinner` | 48 | UI spinner reference | UI component |
| `tool_progress_callback` | 50 | Tool progress handler | System callback |
| `plan_approval_callback` | 55 | Plan approval handler | System callback |
| `undo_initialized` | 57 | Undo system state | System flag |
| `input_sessions` | 62 | Input session tracking | System tracking |
| `current_task` | 63 | Current async task | System reference |
| `is_streaming_active` | 85 | Streaming state flag | System flag |
| `streaming_panel` | 86 | Streaming panel reference | UI component |
| `device_id` | 61 | Device identifier | System ID |

## Existing Helper Methods

**Location:** `src/tunacode/core/state.py`

| Method | Lines | What It Clears |
|--------|-------|----------------|
| `clear_react_scratchpad()` | 227-228 | `react_scratchpad` = `{"timeline": []}` |
| `clear_todos()` | 239-241 | `todos` = `[]` |
| `reset_recursive_state()` | 211-217 | All recursive execution fields |
| `reset_session()` | 243-245 | **Replaces entire SessionState** |

**Important:** `reset_session()` creates a brand new `SessionState` instance but also resets `session_id`, breaking session continuity.

## Related Clear Operations

| Operation | Location | What It Clears | Called Via |
|-----------|----------|---------------|------------|
| `ClearCommand.execute()` | `ui/commands/__init__.py:76` | RichLog, messages, tokens | `/clear` command |
| `react(clear)` | `tools/react.py:71` | ReAct timeline | AI agent tool |
| `todoclear` | `tools/todo.py:214` | Todo list | AI agent tool |
| `clear_all_caches()` | `core/agents/agent_config.py:141` | Agent caches | Testing/utility |

## What a Complete "Fresh Start" Would Require

### Option 1: Selective Clear (Preserve Config)

Clear conversation + runtime state while preserving user configuration:

```python
# Clear these fields:
messages = []
thoughts = []
tool_calls = []
tool_call_args_by_id = {}
react_scratchpad = {"timeline": []}
todos = []
files_in_context = set()
iteration_count = 0
current_iteration = 0
consecutive_empty_responses = 0
batch_counter = 0
total_tokens = 0
last_call_usage = {"prompt_tokens": 0, ...}
session_total_usage = {"prompt_tokens": 0, ...}
request_id = ""
original_query = ""

# Reset recursive state:
state_manager.reset_recursive_state()

# Preserve:
# user_config, current_model, yolo, debug_mode, plan_mode, show_thoughts
# session_id, project_id, created_at (identity)
```

### Option 2: Nuclear Reset (Use Existing Method)

```python
state_manager.reset_session()  # Replaces entire SessionState
# NOTE: This also resets session_id, breaking continuity
```

## Key Findings

1. **CRITICAL: Messages should NOT be cleared**: Current `/clear` deletes messages, then auto-save overwrites disk → conversation lost forever. Users expect `/clear` to reset agent working state, not delete conversation history needed for `/resume`.

2. **Incomplete clearing of agent state**: `/clear` doesn't touch 21 agent working state fields:
   - Conversation artifacts: `thoughts`, `tool_calls`, `todos`
   - Counters: `iteration_count`, `current_iteration`, `batch_counter`, `consecutive_empty_responses`
   - Context: `files_in_context`, `react_scratchpad`, `react_guidance`
   - Recursive execution state: 5 fields for nested task tracking
   - Debug data: `_debug_events`, `_debug_raw_stream_accum`

3. **Helper methods exist but unused**: `clear_react_scratchpad()`, `clear_todos()`, `reset_recursive_state()` are available but not called by `/clear`.

4. **reset_session() is too aggressive**: Replaces entire SessionState including `session_id`, breaking session persistence and file storage.

5. **Documentation is misleading**: "Clear conversation history" is the opposite of what users want - they want "clear agent working memory" not "delete conversation."

6. **Auto-save behavior**: Session auto-saves after every request and on exit, so cleared state immediately persists to disk.

7. **App-level state not touched**: Streaming buffers, pending confirmations, request tasks survive `/clear`.

8. **Agent caches persist**: Both session and module-level agent caches survive `/clear` (likely intentional for performance).

## Knowledge Gaps

1. **User expectations**: No documentation or research on what users actually expect `/clear` to do
2. **Backwards compatibility**: Changing `/clear` behavior may surprise existing users
3. **Session resume interaction**: How does `/clear` interact with `/resume` and saved sessions?

## Recommended Implementation

### Approach: Clear Agent State, Preserve Conversation

Update `/clear` to reset agent working memory while preserving conversation for `/resume`:

```python
async def execute(self, app: TextualReplApp, args: str) -> None:
    session = app.state_manager.session

    # UI clear (visual only)
    app.rich_log.clear()

    # PRESERVE messages - needed for /resume
    # PRESERVE total_tokens - or recalculate from messages

    # Clear agent working state
    session.thoughts = []
    session.tool_calls = []
    session.tool_call_args_by_id = {}
    session.files_in_context = set()

    # ReAct state (use helper)
    app.state_manager.clear_react_scratchpad()
    session.react_forced_calls = 0
    session.react_guidance = []

    # Todos (use helper)
    app.state_manager.clear_todos()

    # Counters
    session.iteration_count = 0
    session.current_iteration = 0
    session.consecutive_empty_responses = 0
    session.batch_counter = 0

    # Request lifecycle
    session.request_id = ""
    session.original_query = ""
    session.operation_cancelled = False

    # Debug instrumentation
    session._debug_events = []
    session._debug_raw_stream_accum = ""

    # Usage tracking - PRESERVE for session cost tracking
    session.last_call_usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
    # Keep session_total_usage - tracks lifetime session cost

    # Recursive execution state (use helper)
    app.state_manager.reset_recursive_state()

    # Update UI and notify
    app._update_resource_bar()
    app.notify("Cleared agent state (UI, thoughts, todos, counters)")

    # Save session to persist the cleared state
    # Messages are preserved, so /resume will still work
    app.state_manager.save_session()
```

**Key changes from original proposal:**
- ❌ Do NOT clear `messages` - needed for `/resume`
- ❌ Do NOT clear `session_total_usage` - tracks session lifetime cost
- ✓ Clear only agent working memory
- ✓ Explicitly save after clear to persist the cleaned state

### What the user sees:

**Before `/clear`:**
```
UI shows: 20 messages, thoughts, todos
Session file: 20 messages saved
```

**After `/clear`:**
```
UI shows: empty (cleared display)
Session file: 20 messages still saved ✓
Agent state: thoughts, todos, counters reset ✓
```

**After `/resume` later:**
```
UI shows: 20 messages restored from disk ✓
Agent state: starts fresh (thoughts, todos empty) ✓
```

### Alternative: UI-only clear with `/clearstate` for full reset

1. `/clear` - Clear UI display only (nothing persisted)
2. `/clearstate` - Clear agent working state (thoughts, todos, counters)

This gives users fine-grained control.

## References

### Code Files

| File | Lines | Purpose |
|------|-------|---------|
| [src/tunacode/ui/commands/__init__.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/6b9ddf4adcd12353b77522850798ee6e4bd679ef/src/tunacode/ui/commands/__init__.py) | 71-80 | ClearCommand implementation |
| [src/tunacode/core/state.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/6b9ddf4adcd12353b77522850798ee6e4bd679ef/src/tunacode/core/state.py) | 36-133 | SessionState dataclass |
| [src/tunacode/core/state.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/6b9ddf4adcd12353b77522850798ee6e4bd679ef/src/tunacode/core/state.py) | 243-245 | reset_session() method |
| [src/tunacode/tools/react.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/6b9ddf4adcd12353b77522850798ee6e4bd679ef/src/tunacode/tools/react.py) | 71-73 | react(clear) tool action |
| [src/tunacode/tools/todo.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/6b9ddf4adcd12353b77522850798ee6e4bd679ef/src/tunacode/tools/todo.py) | 196-222 | todoclear tool |

### Documentation Files

| File | Lines | Content |
|------|-------|---------|
| [src/tunacode/ui/welcome.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/6b9ddf4adcd12353b77522850798ee6e4bd679ef/src/tunacode/ui/welcome.py) | 44 | Welcome screen /clear description |
| [README.md](https://github.com/alchemiststudiosDOTai/tunacode/blob/6b9ddf4adcd12353b77522850798ee6e4bd679ef/README.md) | 92 | README /clear documentation |
| [docs/codebase-map/modules/ui-overview.md](https://github.com/alchemiststudiosDOTai/tunacode/blob/6b9ddf4adcd12353b77522850798ee6e4bd679ef/docs/codebase-map/modules/ui-overview.md) | 123 | UI overview /clear entry |

---

## Additional Search Results

```bash
# Searched for clear-related patterns in .claude/
grep -ri "clear" .claude/
# (No relevant entries found in knowledge base)
```

---

## Summary

**CRITICAL BUG:** `/clear` currently deletes conversation messages, then auto-save overwrites the session file → conversation permanently lost, cannot `/resume` later. This is the opposite of expected behavior.

**Root cause:** Confusion between "clear UI display" vs "clear agent state" vs "delete conversation history"

**Expected behavior:** `/clear` should reset agent working memory (thoughts, todos, counters) while preserving conversation messages for `/resume`

**Implementation path forward:**

1. **Fix critical bug:** STOP clearing `messages` field - preserve for `/resume`
2. **Clear agent state:** Reset 21 working state fields (thoughts, tool calls, todos, counters, ReAct scratchpad, recursive state)
3. **Preserve conversation:** Keep `messages`, `session_total_usage` for session continuity
4. **Helper methods:** Leverage existing `clear_react_scratchpad()`, `clear_todos()`, `reset_recursive_state()`

**Next steps:**
- Implement corrected `/clear` behavior (code provided above)
- Update documentation: "Clear agent working state" not "Clear conversation history"
- Verify auto-save preserves messages after `/clear`
- Test `/clear` → `/resume` workflow

---

*Research completed 2026-01-22 23:15*
