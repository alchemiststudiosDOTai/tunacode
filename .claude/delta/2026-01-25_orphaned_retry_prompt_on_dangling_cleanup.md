---
title: Orphaned retry-prompt parts on dangling tool call cleanup
link: orphaned-retry-prompt-dangling-cleanup
type: delta
path: src/tunacode/core/agents/resume/sanitize.py
depth: 0
seams: [S] state
ontological_relations:
  - relates_to: [[message-history-sanitization]]
  - affects: [[sanitize.py]]
  - fixes: [[orphaned-retry-prompt-bug]]
tags:
  - sanitization
  - tool-calls
  - pydantic-ai
  - message-history
created_at: 2026-01-25T20:15:00Z
updated_at: 2026-01-25T20:15:00Z
uuid: 2e6973a2-6134-4f8e-b181-0900184fd861
---

## Summary

Fixed a bug where `retry-prompt` parts were left orphaned in message history after their corresponding `tool-call` parts were pruned during dangling tool call cleanup. The fix generalizes the filter to remove ANY part with a `tool_call_id` matching a dangling ID, not just `tool-call` parts.

## Context

When a tool call fails (e.g., web_fetch returns 403), pydantic-ai creates a `retry-prompt` part that references the original `tool_call_id`. This is different from a successful `tool-return` part. The sanitization logic at `sanitize.py:111-142` was only filtering parts with `part_kind == "tool-call"`, leaving `retry-prompt` and `tool-return` parts behind.

Log evidence from `tunacode.log` 2026-01-25:
```
[PRUNED] tool_call part: tool=web_fetch id=call_XoXFHWUpi1KujOYx3zHTR1KN
...
history[2].part[0] kind=retry-prompt tool=web_fetch id=call_XoXFHWUpi1KujOYx3zHTR1KN
```

The tool-call was pruned but the retry-prompt referencing it remained, creating an invalid message history.

## Root Cause

`_filter_dangling_tool_calls_from_parts()` used a strict `part_kind == "tool-call"` check to decide what to prune. This missed:
- `retry-prompt` parts (pydantic-ai's error response for failed tool calls)
- `tool-return` parts (though these would be rare to be orphaned)

Both of these part types have a `tool_call_id` attribute that references the original tool call.

## Changes

- **`sanitize.py:111-142`**: Changed `_filter_dangling_tool_calls_from_parts()` to filter ANY part that has a `tool_call_id` attribute matching a dangling ID, regardless of `part_kind`. The function now:
  1. Checks if the part has a `tool_call_id` attribute
  2. If so, checks if that ID is in the dangling set
  3. If so, prunes the part (logging the `part_kind` for debugging)

- **`test_tool_call_lifecycle.py`**: Added `test_remove_dangling_removes_orphaned_retry_prompt_parts()` to cover this specific scenario with a mock `RetryPromptPart`.

## Behavioral Impact

**What users notice:**
- Sessions that previously failed after a tool error (like 403 from web_fetch) followed by user abort will now recover correctly on the next request
- No more "orphaned tool response" errors in the API

**What didn't change:**
- Normal tool call/return matching still works
- Matched tool calls are still preserved
- The detection logic (`find_dangling_tool_calls`) is unchanged - it correctly identifies calls without returns

## Related Cards

- [[dangling-tool-calls-on-abort]] - PR #246, the original fix for dangling tool calls on UserAbortError
- [[gate-6-exception-paths]] - Design principle about exception path handling
