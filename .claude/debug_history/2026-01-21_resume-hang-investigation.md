---
title: Session Resume Hangs After Tool Calls
link: resume-hang-investigation
type: debug
created_at: 2026-01-21T20:45:00Z
updated_at: 2026-01-21T20:45:00Z
tags:
  - resume
  - hang
  - timeout
  - tool-calls
  - pydantic-ai
---

# Session Resume Hangs After Tool Calls

## Symptom

After using `/resume` to load a session that contains tool calls, subsequent requests hang indefinitely (timeout after 30s stream watchdog, then 120s global timeout). Fresh sessions work fine. Sessions without tool calls resume fine.

## Key Debug Output

```
[DEBUG] Stream init: node=ModelRequestNode request_id=786dd9e1 iteration=2 ctx_messages=0 ctx_messages_type=None
[DEBUG] Stream request parts: count=1 type=ModelRequest
[DEBUG] Stream request part[0]: kind=user-prompt content=i am trying to resume (21 chars)
Stream cancelled
[DEBUG] Stream cancelled: events=0 raw_len=0 preview=
[WARNING] Stream watchdog timeout after 30.0s; falling back to non-streaming
```

Critical observation: `ctx_messages=0` - pydantic-ai's internal context has zero messages even though session has 26 messages.

## What We Verified

### Session Data is Clean
- 26 messages with proper request/response alternation
- 7 tool calls, all with matching tool returns (no dangling)
- All messages deserialize correctly via `TypeAdapter(ModelMessage).validate_python()`
- Session ends with a response (valid state)

### Test Matrix

| Scenario | Result |
|----------|--------|
| Fresh session, text only | Works |
| Fresh session, tool calls | Works |
| Resume session, text only | Works |
| Resume session, with tool calls | **HANGS** |

### Code Changes Tested

1. **Iterative cleanup loop** - Made cleanup run until stable (transitive closure)
2. **Fixed `_set_message_tool_calls`** - Added comment that tool_calls is read-only property
3. **Stashed all changes** - Still hangs with original code

## Root Cause Hypothesis

The issue is NOT in the cleanup logic. The session data is valid. The problem is likely:

1. **pydantic-ai message_history not being used** - `ctx_messages=0` suggests the history isn't reaching the model
2. **Serialization/deserialization mismatch** - Messages deserialize but may have subtle differences from live messages
3. **Provider-specific issue** - Chutes/Devstral may reject or hang on certain message patterns

## Evidence Against Common Theories

| Theory | Evidence Against |
|--------|------------------|
| Dangling tool calls | Session has 0 dangling calls |
| Consecutive requests | Proper alternation verified |
| Empty responses | No empty responses |
| Deserialization failure | All 26 messages deserialize |
| Cleanup bug | Hangs with original code too |

## Next Steps

### 1. Add Debug Logging (Priority: High)
Add logging to verify `message_history` is actually being passed to `agent.iter()`:
```python
logger.debug(f"message_history count={len(message_history)}, types={[type(m).__name__ for m in message_history[:3]]}")
```

### 2. Compare Live vs Deserialized Messages (Priority: High)
Check if deserialized messages differ from live messages in ways that affect pydantic-ai:
```python
# After a fresh tool call
live_msg = session_messages[-1]
# After resume
deserialized_msg = session_messages[-1]
# Compare: type, __dict__, model_dump()
```

### 3. Test with Smaller History (Priority: Medium)
Try resuming with only the last N messages to see if size matters:
```python
message_history = list(session_messages[-4:])  # Only last 2 exchanges
```

### 4. Test with Different Provider (Priority: Medium)
Try resuming the same session with Claude or OpenAI to isolate if it's provider-specific.

### 5. Inspect pydantic-ai Internals (Priority: Low)
Check what `agent.iter()` does with `message_history` and why `ctx.messages` might be empty.

## Files Involved

- `src/tunacode/core/agents/main.py` - RequestOrchestrator, cleanup functions
- `src/tunacode/core/state.py` - Session serialization/deserialization
- `src/tunacode/core/agents/agent_components/streaming.py` - Stream handling

## Session Used for Testing

```
Session ID: d748659b-ae50-4c96-b83a-031e15262ebb
Project ID: 0033169849bc63dc
Messages: 26
Tool calls: 7 (all with returns)
Model: chutes:mistralai/Devstral-2-123B-Instruct-2512
```

## Related Issues

- Issue #269: refactor abort recovery fixes
- Commit ad53e0b: fix session resume hangs after user abort
- `.claude/debug_history/2026-01-21_abort-hang-investigation.md`
- `.claude/debug_history/2026-01-21_stream-hang-timeout.md`
