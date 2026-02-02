---
title: "ESC Logic Extraction to ui/esc – Plan"
phase: Plan
date: "2026-02-02T19:29:36Z"
owner: "claude"
parent_research: "memory-bank/research/2026-02-02_12-56-40_esc-key-flow.md"
git_commit_at_plan: "15ce0ed3"
tags: [plan, refactor, ui, esc]
---

## Goal

Make ESC handling clearer and more maintainable by extracting ESC logic into a dedicated, independent module under `src/tunacode/ui/esc/`. The ESC node (handler) should be independent of app internals and depend only on explicit inputs passed in.

**Non-goals:**
- No behavior changes to ESC handling
- No UI changes or visual redesigns
- No new features beyond structural refactor

## Scope & Assumptions

**In scope:**
- Introduce `src/tunacode/ui/esc/` directory
- Extract app-level ESC cascade logic into a standalone component
- Define a minimal, explicit dependency interface (request cancel, shell cancel, editor clear)
- Preserve modal-level ESC behavior (two-phase picker logic, dismiss semantics)

**Out of scope:**
- Changing modal screen behavior
- Adding new key bindings
- Refactoring unrelated UI components

**Assumptions:**
- Existing ESC behavior is correct and should be preserved
- App-level ESC flow can be encapsulated without breaking Textual binding semantics

## Deliverables (DoD)

1. ESC logic lives in `src/tunacode/ui/esc/` with clear public API
2. App ESC binding delegates to the new ESC handler
3. Modal screen ESC logic remains unchanged and documented
4. No new mypy errors
5. Ruff clean (`uv run ruff check .`)

## Readiness (DoR)

- [x] Research doc complete (ESC flow mapping)
- [x] Target files identified
- [ ] Proposed module interface reviewed

## Proposed Module Design

- **Module path:** `src/tunacode/ui/esc/`
- **Primary entry:** `EscHandler` (or similar) with a single `handle_escape(...)` method
- **Dependencies passed explicitly:**
  - `current_request_task` (or a cancel callable)
  - `shell_runner` (or a cancel callable + is_running)
  - `editor` (or a clear callable + has_content/has_paste_buffer)
- **No hidden state:** all state required for decisions is passed in or queried via explicit interfaces
- **App integration:** `TunaApp.action_cancel_request()` delegates to `EscHandler` and performs no logic itself

## Work Breakdown (Tasks)

| Task | ID | Summary | File(s) | Notes |
|------|-----|---------|---------|-------|
| T1 | tk-new | Define `ui/esc` package + handler API | `src/tunacode/ui/esc/__init__.py` | Public interface only |
| T2 | tk-new | Move app-level ESC cascade into handler | `src/tunacode/ui/app.py`, `src/tunacode/ui/esc/handler.py` | Preserve cascade order |
| T3 | tk-new | Add minimal protocol/typing for dependencies | `src/tunacode/ui/esc/types.py` | Explicit inputs only |
| T4 | tk-new | Update docs/comments to reflect new location | `src/tunacode/ui/app.py` | Avoid behavior changes |

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| Binding priority behavior changes | High | Low | Keep `priority=True` binding in app; delegate only | ESC fails to cancel as before |
| Dependency coupling creeps back | Medium | Medium | Enforce explicit inputs in handler API | Handler starts importing app state |
| Behavior drift in cascade order | High | Low | Mirror exact order and early returns | ESC clears input when request running |

## Test Strategy

- **No new tests** (behavioral equivalence)
- Manual sanity checks:
  - ESC cancels request task first
  - ESC cancels shell next
  - ESC clears editor only when nothing else active
  - Modal ESC behavior unchanged
- Run: `uv run pytest` (if required by workflow)

## References

- Research doc: `memory-bank/research/2026-02-02_12-56-40_esc-key-flow.md`
- Current ESC logic: `src/tunacode/ui/app.py` (binding + cascade)
- Modal ESC logic: `src/tunacode/ui/screens/*.py`
- Editor clear logic: `src/tunacode/ui/widgets/editor.py`
- Shell cancel logic: `src/tunacode/ui/shell_runner.py`
