---
title: Extract ESC Handling into ui/esc Module
link: esc-handler-extraction
type: delta
path: src/tunacode/ui/esc/handler.py
depth: 0
seams: [M, E]
ontological_relations:
  - relates_to: [[ui-esc-handling]]
  - affects: [[textual-app]]
tags:
  - refactor
  - ui
  - esc
  - modularity
created_at: 2026-02-02T19:34:51Z
updated_at: 2026-02-02T19:34:51Z
uuid: 63413ef6-ecbc-4f26-ba23-a9db43ce83b0
---

## Summary

Moved the app-level ESC cancellation cascade into a dedicated `ui/esc` module and delegated `action_cancel_request()` to an explicit handler. This isolates ESC logic from app internals and makes the dependency inputs explicit.

## Context

- New module: `src/tunacode/ui/esc/`
- Caller: `src/tunacode/ui/app.py` now delegates ESC handling

## Changes

- Added `EscHandler` with explicit dependency inputs for request task, shell runner, and editor state.
- Added dependency protocols in `ui/esc/types.py` to avoid coupling with concrete UI classes.
- Updated `TextualReplApp.action_cancel_request()` to delegate to the handler.

## Behavioral Impact

- No user-facing behavior changes.
- ESC handling order and early-return cascade remain identical.
- Modal ESC behavior unchanged (still handled in modal screens).

## Related Cards

- [[ui-esc-handling]]
- [[textual-app]]
