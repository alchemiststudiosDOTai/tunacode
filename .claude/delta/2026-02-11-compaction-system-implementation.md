---
title: Compaction system implemented across core, agent loop, and UI
type: delta
link: compaction-system-implementation
path: src/tunacode/core/compaction
depth: 0
seams: [A, S, M]
ontological_relations:
  - relates_to: [[context-management]]
  - affects: [[core]]
  - affects: [[ui]]
  - affects: [[session-persistence]]
  - affects: [[error-handling]]
tags:
  - compaction
  - context-window
  - tinyagent
  - ui
  - persistence
created_at: 2026-02-11T22:45:00-06:00
updated_at: 2026-02-11T22:45:00-06:00
uuid: 89cf0c58-0f25-4d6f-8a44-02d8b802add4
---

# Compaction system implemented across core, agent loop, and UI

## Summary

Added end-to-end context compaction with retention-window summarization, session-level compaction metadata, transform-context wiring, overflow retry, and a manual `/compact` command with UI feedback.

## Changes

- Added `src/tunacode/core/compaction/` package:
  - `types.py`: `CompactionRecord` dataclass with strict `to_dict()` / `from_dict()`.
  - `prompts.py`: fresh and iterative structured summary prompts.
  - `summarizer.py`: backward retention boundary, transcript serialization, tool-result truncation, summary generation.
  - `controller.py`: `CompactionController` policy/orchestration, fail-safe behavior, idempotency guard, summary injection, and OpenRouter summarization backend.
- Integrated into request loop:
  - `agent_config.py`: wired tinyagent `transform_context`.
  - `main.py`: pre-request compaction and one-shot overflow compact+retry path.
- Added session persistence support:
  - `SessionState.compaction` and `_compaction_controller`.
  - save/load of optional `compaction` field in session JSON.
- Added UI integration:
  - `/compact` command (`ui/commands/compact.py`) and command registration.
  - `ResourceBar` compaction indicator: `Compacting...`.
  - App callback plumbing to toggle compaction status in real time.
- Added new exception:
  - `ContextOverflowError` with recovery commands.
- Added tests:
  - `tests/test_compaction.py` integration flow + legacy session compatibility.
  - `tests/unit/core/test_exceptions.py` coverage for new overflow exception.

## Verification

- `uv run ruff check --fix .`
- `uv run pytest`

Result: full suite passing (`429 passed, 1 skipped`).

## Behavioral impact

- Long sessions can be compacted automatically before requests.
- Overflow errors now trigger a forced compaction retry once.
- Users can force compaction manually with `/compact`.
- Session compaction metadata survives save/load round trips.
