---
title: "Fix /clear to preserve conversation messages for /resume"
link: "clear-command-preserve-messages"
type: "delta"
path: "src/tunacode/ui/commands/__init__.py"
depth: 0
seams: [E, S]
ontological_relations:
  - relates_to: [[session-management]]
  - affects: [[ui-commands, state-management]]
  - fixes: [[clear-command-data-loss]]
tags:
  - bugfix
  - clear-command
  - session-persistence
  - ux
created_at: "2026-01-22T23:30:00Z"
updated_at: "2026-01-22T23:30:00Z"
uuid: "01935f00-a1b2-7c00-9e7c-d9e1a4c8e3e2"
---

# Delta – Fix /clear to preserve conversation messages for /resume

**Date:** 2026-01-22
**Type:** Bugfix
**Severity:** Critical - Data Loss

## Summary

Fixed critical data loss bug where `/clear` deleted conversation messages, causing auto-save to overwrite session files with empty messages. Users could never `/resume` their conversation after clearing. Now `/clear` resets agent working memory (thoughts, todos, counters) while preserving conversation messages for later resume.

## Context

Users reported that `/clear` should "clear state" not "delete conversation history." Investigation revealed:

1. `/clear` deleted `messages` field
2. Auto-save ran after every request, persisting empty messages to disk
3. `/resume` would load empty conversation → data permanently lost
4. Only 2 of 42 SessionState fields were cleared, leaving agent state dirty

**Root cause:** Confusion between three distinct operations:
- Clear UI display (visual)
- Clear agent working memory (thoughts, todos, counters)
- Delete conversation history (destructive, should require confirmation)

## Root Cause

The original `/clear` implementation:
```python
app.rich_log.clear()
session.messages = []              # ✗ WRONG - deletes conversation
session.total_tokens = 0
```

Combined with auto-save behavior:
- Auto-save after every request
- Auto-save on app exit
- No backup before clearing

Result: Messages deleted from memory → auto-save → disk overwritten → data lost forever.

## Changes

### Code Changes

**File:** `src/tunacode/ui/commands/__init__.py`

1. **Removed destructive operations:**
   - ✗ Stopped clearing `messages` field
   - ✗ Stopped clearing `total_tokens` field

2. **Added comprehensive agent state clearing (21 fields):**
   - Conversation artifacts: `thoughts`, `tool_calls`, `tool_call_args_by_id`, `files_in_context`
   - ReAct state: `react_scratchpad`, `react_forced_calls`, `react_guidance` (using helpers)
   - Todos: cleared via `clear_todos()` helper
   - Counters: `iteration_count`, `current_iteration`, `consecutive_empty_responses`, `batch_counter`
   - Request lifecycle: `request_id`, `original_query`, `operation_cancelled`
   - Debug data: `_debug_events`, `_debug_raw_stream_accum`
   - Usage: `last_call_usage` (preserved `session_total_usage` for lifetime tracking)
   - Recursive state: via `reset_recursive_state()` helper

3. **Added explicit save:**
   - Call `save_session()` after clearing to persist the cleaned state
   - Messages preserved in save → `/resume` still works

4. **Updated notification:**
   - Old: "Cleared conversation history"
   - New: "Cleared agent state (messages preserved for /resume)"

### Documentation Changes

**Files Updated:**
- `README.md` - Updated command table
- `src/tunacode/ui/welcome.py` - Updated welcome screen text
- `docs/codebase-map/modules/ui-overview.md` - Updated command description

**Before:**
> `/clear` - Clear conversation history

**After:**
> `/clear` - Clear agent working state (UI, thoughts, todos) - messages preserved for /resume

## Behavioral Impact

### What Users See

**Before `/clear` (broken behavior):**
```
User: Has 20 message conversation
User: Runs /clear
Result: Messages deleted from memory + disk
User: Later runs /resume
Result: Empty conversation loaded (DATA LOST)
```

**After `/clear` (fixed behavior):**
```
User: Has 20 message conversation
User: Runs /clear
Result: UI cleared, agent state reset, messages preserved on disk
User: Later runs /resume
Result: 20 messages restored ✓, agent state starts fresh ✓
```

### What Changed

**Cleared (21 fields):**
- Agent working memory
- Visual display
- Counters and tracking state

**Preserved (21 fields):**
- Conversation messages ← **KEY FIX**
- User configuration
- Session identity
- System references

### What Didn't Change

- Auto-save behavior still runs after every request
- `/resume` command unchanged
- Session file format unchanged
- Agent cache behavior unchanged

## How We Missed This

1. **No test coverage** for `/clear` → `/resume` workflow
2. **Ambiguous naming** - "clear conversation" suggested clearing messages
3. **No user research** on expected behavior
4. **No confirmation dialog** for destructive operations
5. **Auto-save is silent** - users didn't realize data was being deleted

## Prevention

1. **Testing:** Add integration test for `/clear` → `/resume` workflow
2. **Naming:** Use precise terminology - "agent state" not "conversation"
3. **Confirmation:** Consider adding confirmation for truly destructive operations
4. **Feedback:** Show exactly what was cleared in notification
5. **Backup:** Consider backup-before-clear for sensitive operations

## Related Cards

- [[memory-bank/research/2026-01-22_21-50-08_clear-command-behavior-analysis]]
- [[session-management]]
- [[state-manager]]

---

*Delta recorded 2026-01-22 23:30*
