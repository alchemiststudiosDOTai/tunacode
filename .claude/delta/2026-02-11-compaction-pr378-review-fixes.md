---
title: PR #378 compaction review fixes (single-writer, outcome contract, edge tests)
type: delta
link: compaction-pr378-review-fixes
path: src/tunacode/core/compaction
depth: 0
seams: [A, S, M]
ontological_relations:
  - relates_to: [[context-management]]
  - affects: [[core]]
  - affects: [[ui]]
  - affects: [[tests]]
  - affects: [[pr-hygiene]]
tags:
  - compaction
  - review-fixes
  - error-handling
  - contracts
  - testing
created_at: 2026-02-11T13:09:52-06:00
updated_at: 2026-02-11T13:09:52-06:00
uuid: 0ba5f078-70a9-44e2-b81c-f9ba7111c32b
---

# PR #378 compaction review fixes

## Summary

Implemented PR review follow-ups for compaction with low-risk, compaction-scoped diffs:

- Compaction controller no longer mutates `session.conversation.messages` directly.
- One shared apply path (`apply_compaction_messages`) now owns compaction message writes.
- Compaction returns an explicit structured outcome (`status`, `reason`, `detail`, `messages`).
- Capability skips (unsupported provider / missing API key) now surface explicit notices and structured log metadata.
- Threshold equality policy is explicitly documented and test-locked.
- Added targeted edge-case tests for boundary safety, fail-safe fallback, and overflow detection contract.
- Removed unrelated pydantic-ai memory-bank files from PR scope.

## Key code changes

- `src/tunacode/core/compaction/controller.py`
  - Added `CompactionOutcome` usage and stable reason/status handling.
  - Removed UI notice callback coupling.
  - Added `build_compaction_notice()` and shared `apply_compaction_messages()` writer path.
- `src/tunacode/core/compaction/types.py`
  - Added compaction status/reason constants and `CompactionOutcome` contract.
- `src/tunacode/core/agents/main.py`
  - Updated orchestration to consume outcomes and emit notices from outcome contract.
  - Compaction-related message writes now go through shared apply path.
- `src/tunacode/ui/commands/compact.py`
  - `/compact` consumes structured outcomes and emits explicit skip/failure notices.
- `src/tunacode/ui/commands/base.py`, `src/tunacode/ui/commands/__init__.py`
  - `CompactCommand` now inherits `Command`; cast workaround removed.
- `src/tunacode/core/compaction/summarizer.py`
  - Documents inclusive threshold equality policy (`>= keep_recent_tokens`).

## Tests added/updated

- `tests/test_compaction.py`
- `tests/unit/core/test_compaction_summarizer.py`
- `tests/unit/core/test_compaction_controller_outcomes.py`
- `tests/unit/core/test_context_overflow_detection.py`

Coverage focus:

- threshold equality contract
- snap-to-zero boundary behavior
- tool call/result boundary safety
- empty-history force-compaction skip outcome
- summarizer failure fallback contract
- capability skip reason codes and notices
- overflow classifier behavior

## Verification

- `uv run ruff check --fix .`
- `uv run ruff check .`
- `uv run pytest tests/test_compaction.py tests/unit/core/test_compaction_summarizer.py tests/unit/core/test_compaction_controller_outcomes.py tests/unit/core/test_context_overflow_detection.py -q`
- `uv run pytest tests/architecture/test_layer_dependencies.py -q`
