# Bug: Messages Not Persisted on Error/Abort

## Summary

Messages are only saved after successful completion of the agent loop. Any error, abort, or cancellation causes ALL messages to be lost, even if the conversation ran for many iterations.

## Root Cause

**Location:** `src/tunacode/core/agents/main.py:417-430`

`_persist_run_messages()` is called at line 417 ONLY after the iteration loop completes successfully. The `except` block at lines 422-430 does NOT persist messages - it only cleans up dangling tool calls.

```python
try:
    async with agent.iter(...) as agent_run:
        for node in agent_run:
            # iterations happen, usage/react updated

        # ONLY RUNS IF NO EXCEPTION
        self._persist_run_messages(agent_run, baseline_message_count)

except (UserAbortError, asyncio.CancelledError):
    # Messages NOT persisted here!
    _remove_dangling_tool_calls(...)
    raise
```

## Impact

- User can have a 20-minute conversation
- Error happens on iteration 10
- All 10 iterations of messages = lost
- Session shows activity (tokens, react entries, cost) but empty messages

## Evidence

Found 5+ sessions on disk with:
- `messages: []` (empty)
- `prompt_tokens: 415,708` (hundreds of thousands)
- `react_scratchpad.timeline: 8 entries` (iterations ran)
- `cost: $0.06` (money charged)

Example session: `951a0700590b351a_f62729e2-57d5-42b2-bcc2-864a2155a85b.json`

## Secondary Issue

**Location:** `src/tunacode/core/state.py:271-273`

```python
with suppress(TypeError, ValueError, AttributeError):
    result.append(msg_adapter.dump_python(msg, mode="json"))
```

Messages that fail to serialize are silently dropped. Violates "fail fast, fail loud" principle.

## Proposed Fix

Persist messages in the `except` block before re-raising:

```python
except (UserAbortError, asyncio.CancelledError):
    # Persist whatever messages we have so far
    try:
        run_messages = list(agent_run.all_messages())
        self.state_manager.session.messages = run_messages
    except Exception:
        pass  # best effort

    # Clean up dangling tool calls
    cleanup_applied = _remove_dangling_tool_calls(...)
    raise
```

## Files to Modify

1. `src/tunacode/core/agents/main.py` - Add message persistence in except block
2. `src/tunacode/core/state.py` - Consider logging serialization failures instead of silent suppress

## Related

- Gate 6: Exception Paths Are First-Class (CLAUDE.md)
- PR #246: Dangling tool calls bug (similar exception-path issue)
