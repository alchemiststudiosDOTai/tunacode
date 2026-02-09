---
title: Phase 6: tinyagent-only messaging utilities (token counter + sanitize)
link: tun-1658-phase6-messaging-normalization
type: delta
path: src/tunacode/utils/messaging/
depth: 1
seams: [D, M, S]
ontological_relations:
  - relates_to: [[tinyagent-migration]]
  - affects: [[src/tunacode/utils/messaging]]
  - affects: [[src/tunacode/core/agents/resume]]
  - fixes: [[pydantic-ai-message-assumptions-in-messaging]]
tags:
  - messaging
  - tinyagent
  - resume
created_at: 2026-02-07T22:55:04Z
updated_at: 2026-02-07T22:55:04Z
uuid: 015cc02f-ed29-4132-84c1-5510bb904ae8
---

## Summary
Normalized message utilities to operate on tinyagent dict messages (role + content[type]) only. Token estimation and resume sanitization no longer attempt to interpret legacy pydantic-ai message objects, aligning with the “full rip-out” direction.

## Context
During the tun-1658 tinyagent migration, history is persisted as tinyagent dicts:
- assistant: `{role: "assistant", content: [{type: "text"|"thinking"|"tool_call"|"image", ...}]}`
- tool result: `{role: "tool_result", tool_call_id: "...", content: [...]}`

Older utilities still had defensive support for pydantic-ai style `parts`/`part_kind` shapes.

## Root Cause
Utility modules (notably token counting and some sanitize logic) were written to accept polymorphic message inputs and silently “do something” for objects with `.parts`/`.content`. With tinyagent dict messages, this both (a) masked stale session formats and (b) caused unnecessary canonicalization overhead.

## Changes
- `src/tunacode/utils/messaging/token_counter.py`
  - Now supports **only** tinyagent dict messages and `CanonicalMessage`.
  - Token estimation runs via `to_canonical()` + canonical parts, and counts tool-call metadata (`tool_name`, `tool_call_id`, `args`) heuristically.
- `src/tunacode/core/agents/resume/sanitize.py`
  - `_is_request_message()` is now role-based on dict messages (no canonical conversion).
  - Removed `to_canonical` dependency from sanitize (canonicalization remains in `find_dangling_tool_calls()` only).
- `src/tunacode/utils/messaging/adapter.py`
  - Refactored `to_canonical()` / `from_canonical()` into smaller helpers to satisfy ruff complexity constraints (no behavior change intended).
- Tests updated to use tinyagent message shapes:
  - `tests/unit/utils/test_token_counter.py`
  - `tests/unit/test_sanitize_canonicalization.py`

## Behavioral Impact
- Token estimation now fails loudly if non-tinyagent message objects appear in history.
- Resume sanitization no longer performs redundant canonical conversions when scanning for consecutive request messages.
- No user-facing UI rendering changes yet (handled in Phase 7).

## Related Cards
- [[tun-1658-phase5-cleanup]]
