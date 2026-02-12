---
title: Guard final response rendering to current request + fail-loud streaming UI
type: delta
link: ui-response-render-guard-stream-fail-loud
path: src/tunacode/ui/app.py
depth: 0
seams: [S]
ontological_relations:
  - affects: [[ui]]
  - affects: [[agent-loop]]
  - relates_to: [[streaming]]
tags:
  - ui
  - textual
  - streaming
  - error-handling
  - repl
created_at: 2026-02-11T23:02:27-06:00
updated_at: 2026-02-11T23:02:27-06:00
uuid: 6a31d784-974b-4c8c-b7e9-e2948405407e
---

# Guard final response rendering to current request + fail-loud streaming UI

## Summary

Fixed two REPL UI correctness issues in `TextualReplApp`:

1. Prevent stale/previous assistant responses from being re-rendered when a request does not complete successfully.
2. Removed silent exception swallowing in streaming UI updates so UI failures surface instead of being ignored.

## Changes

- Updated `src/tunacode/ui/app.py`:
  - `_process_request(...)`
    - Added `request_succeeded` flag.
    - Captures latest assistant response signature before request start.
    - Renders final assistant panel only when:
      - request succeeded, and
      - latest assistant response changed during the request.
  - Replaced `_get_latest_response_text` with `_get_latest_assistant_response` returning `(text, signature)` for change detection.
  - `_streaming_callback(...)`
    - Removed `try/except Exception: pass` block.
    - Streaming UI exceptions now propagate (fail loud).

## Verification

- `uv run ruff check src/tunacode/ui/app.py`
