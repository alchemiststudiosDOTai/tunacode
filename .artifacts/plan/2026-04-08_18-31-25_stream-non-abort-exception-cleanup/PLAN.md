---
title: "stream non-abort exception cleanup implementation plan"
link: "stream-non-abort-exception-cleanup-plan"
type: implementation_plan
ontological_relations:
  - relates_to: [[stream-non-abort-exception-cleanup-research]]
tags: [plan, stream-exceptions, agents, coding]
uuid: "4fc2200f-59f9-43d4-863b-48557582a17e"
created_at: "2026-04-08T18:32:08-05:00"
parent_research: ".artifacts/research/2026-04-08_18-29-14_stream-non-abort-exception-cleanup.md"
git_commit_at_plan: "91a9022a"
---

## Goal

- Ensure any non-abort exception raised while a stream attempt is active cleans up dangling tool-call state the same way user aborts do, while preserving the original exception.
- Keep cleanup baseline selection correct for both the initial stream and the forced-compaction retry stream.
- Out of scope: release workflow changes, user-facing docs, resume-history algorithm changes beyond maintaining current parity, and broad tool-registry refactors.

## Scope & Assumptions

- IN scope: `RequestOrchestrator` stream exception routing, `_TinyAgentStreamState` data needed for cleanup ownership, and focused unit regressions for callback/message-update failures.
- IN scope: retry-path correctness when `_retry_after_context_overflow_if_needed()` starts a second stream with a different `baseline_message_count`.
- OUT of scope: changing the synthetic `"Tool execution aborted"` payload, changing `run_cleanup_loop()` semantics, or introducing new architecture-layer dependencies.
- Assumptions: the existing abort cleanup behavior in `src/tunacode/core/agents/main.py` is the behavioral source of truth; `tests/unit/core/test_request_orchestrator_parallel_tools.py` remains the right place for stream cleanup regressions; the working tree at plan time contains only the untracked `.artifacts/research/` directory.

## Deliverables

- A shared interrupted-stream cleanup path that can be invoked for user aborts and unexpected stream exceptions without duplicating logic.
- Retry-aware stream invocation code that uses the correct message baseline for cleanup on every stream attempt.
- Focused regression coverage for callback failures, retry-path cleanup, and `_run_stream()` logging on failing streams.

## Readiness

- Preconditions: the parent research artifact exists at `.artifacts/research/2026-04-08_18-29-14_stream-non-abort-exception-cleanup.md`.
- Preconditions: current plan snapshot is based on Git commit `91a9022a`.
- Preconditions: `docs/git/practices.md` has already been read for this session before Git inspection.
- Preconditions: no cleanup of untracked artifacts is required for this work.

## Milestones

- M1: Stream-state contract and shared cleanup path are in place.
- M2: Initial-stream and retry-stream exception routing use the shared cleanup path.
- M3: Core regression tests cover callback failures and retry-baseline correctness.
- M4: Stream-phase debug logging regressions cover failing streams without false-success logs.

## Ticket Index

<!-- TICKET_INDEX:START -->

| Task | Title | Ticket |
|---|---|---|
| T001 | bug: store per-stream baseline and centralize interruption cleanup | [tickets/T001.md](tickets/T001.md) |
| T002 | bug: route unexpected stream exceptions through cleanup for every stream attempt | [tickets/T002.md](tickets/T002.md) |
| T003 | test: add regression coverage for tool callback failures during stream tool events | [tickets/T003.md](tickets/T003.md) |
| T004 | test: add retry-path regression coverage for cleanup baseline correctness | [tickets/T004.md](tickets/T004.md) |
| T005 | test: add failing-stream logging regression coverage for message-update exceptions | [tickets/T005.md](tickets/T005.md) |

<!-- TICKET_INDEX:END -->

## Work Breakdown (Tasks)

### T001: bug: store per-stream baseline and centralize interruption cleanup

**Summary**: Extend the active stream state so cleanup logic can recover the correct `baseline_message_count` for the specific stream attempt that failed, then move the common abort cleanup steps behind one shared helper used by all interruption paths.

**Owner**: core

**Estimate**: 2h

**Dependencies**: none

**Target milestone**: M1

**Acceptance test**: `uv run pytest tests/unit/core/test_request_orchestrator_parallel_tools.py -k uses_active_stream_baseline_for_cleanup`

**Files/modules touched**:
- src/tunacode/core/agents/helpers.py
- src/tunacode/core/agents/main.py
- tests/unit/core/test_request_orchestrator_parallel_tools.py

**Steps**:
1. Add a per-attempt cleanup baseline field to `_TinyAgentStreamState` in `src/tunacode/core/agents/helpers.py`, keeping the dataclass limited to state required by stream cleanup.
2. Populate that field from `_run_stream()` in `src/tunacode/core/agents/main.py` so the initial stream and any forced-compaction retry each record their own baseline.
3. Extract the shared cleanup sequence from `_handle_abort_cleanup()` into a helper that reads unresolved tool IDs and the cleanup baseline from `self._active_stream_state` when present.
4. Keep user-abort behavior unchanged: dangling tool calls are patched forward, in-flight registry entries are removed, partial assistant output is appended once, and `_active_stream_state` is cleared.

### T002: bug: route unexpected stream exceptions through cleanup for every stream attempt

**Summary**: Catch non-abort exceptions around each `_run_stream()` invocation, invoke the shared cleanup helper with the correct agent/baseline context, and re-raise the original exception without converting it to an abort or `AgentError`.

**Owner**: core

**Estimate**: 2h

**Dependencies**: T001

**Target milestone**: M2

**Acceptance test**: `uv run pytest tests/unit/core/test_request_orchestrator_parallel_tools.py -k reraises_non_abort_exception_after_stream_cleanup`

**Files/modules touched**:
- src/tunacode/core/agents/main.py
- tests/unit/core/test_request_orchestrator_parallel_tools.py

**Steps**:
1. Introduce a small wrapper in `src/tunacode/core/agents/main.py` that executes one stream attempt and handles cleanup only when an unexpected exception escapes while a stream state is active.
2. Use that wrapper for the initial `_run_stream()` call in `_run_impl()` and for the retry `_run_stream()` call inside `_retry_after_context_overflow_if_needed()`.
3. Preserve current handling for `UserAbortError`, `asyncio.CancelledError`, normal stream completion, and post-stream `AgentError` checks; only unexpected in-stream exceptions should take the new path.
4. Re-raise the original exception object after cleanup so callers and tests still see the true failure cause.

### T003: test: add regression coverage for tool callback failures during stream tool events

**Summary**: Add focused unit coverage proving that exceptions from `tool_start_callback` and `tool_result_callback` trigger interruption cleanup, clear the registry/active state, and preserve the original callback exception.

**Owner**: tests

**Estimate**: 1.5h

**Dependencies**: T002

**Target milestone**: M3

**Acceptance test**: `uv run pytest tests/unit/core/test_request_orchestrator_parallel_tools.py -k callback_failure_cleanup`

**Files/modules touched**:
- tests/unit/core/test_request_orchestrator_parallel_tools.py

**Steps**:
1. Build fake callbacks that raise `RuntimeError("callback blew up")` during tool-start and tool-end handling.
2. Drive `RequestOrchestrator` through a stream sequence that registers at least one tool call and accumulates partial assistant text before the callback failure fires.
3. Assert that the failure path clears `_active_stream_state`, removes unresolved tool IDs from `session.runtime.tool_registry`, appends exactly one synthetic aborted `ToolResultMessage` when needed, and preserves any already-completed tool results.
4. Assert that the original `RuntimeError("callback blew up")` is re-raised to the caller.

### T004: test: add retry-path regression coverage for cleanup baseline correctness

**Summary**: Add a unit test that simulates a context-overflow retry stream failing mid-turn, and verify cleanup only patches the retry slice rather than rewriting messages restored from the pre-request history.

**Owner**: tests

**Estimate**: 1.5h

**Dependencies**: T002

**Target milestone**: M3

**Acceptance test**: `uv run pytest tests/unit/core/test_request_orchestrator_parallel_tools.py -k retry_stream_cleanup_baseline`

**Files/modules touched**:
- tests/unit/core/test_request_orchestrator_parallel_tools.py

**Steps**:
1. Create a fake agent/orchestrator scenario where the first stream completes into a context-overflow state and `_retry_after_context_overflow_if_needed()` launches a second stream with a new baseline.
2. Make the retry stream raise a non-abort exception after starting a tool call so cleanup has to patch dangling tool calls.
3. Assert that messages from `pre_request_history` remain untouched, only retry-turn messages receive injected aborted tool results, and the retry stream's in-flight registry entries are removed.
4. Keep the assertion surface narrow to baseline slicing and cleanup side effects, not full compaction behavior.

### T005: test: add failing-stream logging regression coverage for message-update exceptions

**Summary**: Add stream-phase debug coverage for exceptions raised during message-update callbacks so `_run_stream()` logs the stream start and first event, but does not emit misleading successful end/request-complete lines before the exception escapes.

**Owner**: tests

**Estimate**: 1h

**Dependencies**: T002

**Target milestone**: M4

**Acceptance test**: `uv run pytest tests/unit/core/test_stream_phase_debug.py -k failing_stream_logging`

**Files/modules touched**:
- tests/unit/core/test_stream_phase_debug.py

**Steps**:
1. Reuse the fake logger/fake agent harness in `tests/unit/core/test_stream_phase_debug.py` and add a streaming callback that raises during a `MessageUpdateEvent`.
2. Execute `_run_stream()` through the failure case without converting it into a successful stream completion.
3. Assert the logger captures the start and first-event entries, omits `"Stream: end ..."` and `"Request complete (...)"` lines, and lets the original exception escape.
4. Keep the test isolated to logging behavior so cleanup assertions remain in `test_request_orchestrator_parallel_tools.py`.

## Risks & Mitigations

- Risk: cleanup may run with the wrong baseline during forced-compaction retry and inject synthetic tool results into the wrong message slice.
  Mitigation: make the active stream state store the per-attempt baseline and add a retry-specific regression test before changing exception routing.
- Risk: a broad `except Exception` could accidentally swallow `UserAbortError`, `asyncio.CancelledError`, or post-stream `AgentError` handling.
  Mitigation: isolate the new wrapper to in-stream failures only and explicitly re-raise the original exception object.
- Risk: callback-failure tests may overfit to private helper internals instead of observable behavior.
  Mitigation: assert conversation messages, registry contents, `_active_stream_state`, and raised exceptions rather than implementation details.
- Risk: logging tests may become brittle if they assert unrelated lifecycle lines.
  Mitigation: assert only the presence or absence of the start/first-event/end/request-complete messages relevant to failing streams.

## Test Strategy

- Add one focused regression per task rather than broad integration coverage.
- Prefer fake agents/callbacks over full tinyagent integration to keep failure injection deterministic.
- Keep new tests in the existing orchestrator/debug test modules to avoid creating another stream-test surface.

## References

- Research doc: `.artifacts/research/2026-04-08_18-29-14_stream-non-abort-exception-cleanup.md`
- `src/tunacode/core/agents/main.py:188` for `_run_impl()`
- `src/tunacode/core/agents/main.py:247` for current abort-only exception handling
- `src/tunacode/core/agents/main.py:373` for in-flight registry cleanup
- `src/tunacode/core/agents/main.py:388` for dangling tool-call patch-forward logic
- `src/tunacode/core/agents/main.py:481` for tool-start mutations
- `src/tunacode/core/agents/main.py:505` for tool-end mutations
- `src/tunacode/core/agents/main.py:652` for `_run_stream()`
- `src/tunacode/core/agents/main.py:708` for current success-only active-state clearing
- `src/tunacode/core/agents/main.py:744` for `_handle_abort_cleanup()`
- `src/tunacode/core/agents/helpers.py:35` for `_TinyAgentStreamState`
- `src/tunacode/core/types/state_structures.py:57` for `RuntimeState.tool_registry`
- `src/tunacode/core/types/tool_registry.py:33` for `ToolCallRegistry`
- `src/tunacode/core/agents/resume/sanitize.py:396` for resume dangling-tool cleanup parity
- `src/tunacode/core/agents/resume/sanitize.py:444` for iterative resume cleanup
- `tests/unit/core/test_request_orchestrator_parallel_tools.py:194` for current abort cleanup coverage
- `tests/unit/core/test_stream_phase_debug.py:40` for current `_run_stream()` logging coverage

## Final Gate

- **Output summary**: `.artifacts/plan/2026-04-08_18-31-25_stream-non-abort-exception-cleanup/`, 4 milestones, 5 tickets
- **Next step**: proceed to execute-phase with `.artifacts/plan/2026-04-08_18-31-25_stream-non-abort-exception-cleanup/PLAN.md`
