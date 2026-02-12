---
title: "Re-implement Streaming with tinyagent – Execution Plan"
phase: Plan
date: "2026-02-11T00:00:00"
owner: context-engineer
parent_research: "memory-bank/research/2026-02-11_00-00-00_tinyagent_streaming_reimplementation.md"
git_commit_at_plan: "2239711d"
tags: [plan, streaming, tinyagent, ui]
---

## Goal

Enable real-time streaming display in the TUI by connecting the existing core streaming infrastructure to the UI layer. The streaming callback is currently `None`; this plan implements a callback that updates the UI incrementally as tokens arrive from tinyagent.

**Non-goals:** Pause/resume, tool panel anchoring, markdown rendering optimization (deferred to Phase 2).

---

## Scope & Assumptions

**In Scope:**
- Create `streaming_callback` in `app.py` that updates `self.streaming_output`
- Pass callback to `process_request()` instead of `None`
- Handle streaming lifecycle (start, update, end/cleanup)
- Add throttled updates (100ms) to reduce visual churn

**Out of Scope:**
- Pause/resume functionality (Phase 3)
- Tool panel chronological positioning (Phase 3)
- Markdown syntax highlighting during streaming (use plain text)
- Changes to core agent loop (already supports streaming)

**Assumptions:**
- tinyagent's `agent.stream()` yields `text_delta` events correctly
- `self.streaming_output` Static widget exists and CSS `.active` class works
- Current cleanup in finally block (lines 232-233) is correct pattern to extend

---

## Deliverables (DoD)

| # | Deliverable | Acceptance Criteria |
|---|-------------|---------------------|
| 1 | Streaming callback | `app.py` has `_streaming_callback()` that accumulates text and updates UI |
| 2 | Throttled updates | Updates occur at most every 100ms during streaming |
| 3 | Panel lifecycle | Streaming panel shows on first chunk, hides on completion/error |
| 4 | Working demo | User can run a request and see tokens appear in real-time |

---

## Readiness (DoR)

- [x] Research document exists and is fresh (no code drift)
- [x] Core streaming infrastructure verified working
- [x] UI widget exists with CSS support
- [ ] **BLOCKER:** None — ready to start immediately

---

## Milestones

| Milestone | Target | Description |
|-----------|--------|-------------|
| M1 | 30 min | Basic streaming callback that updates UI on every chunk |
| M2 | 1 hour | Add throttled updates (100ms) and proper lifecycle |
| M3 | 1.5 hours | Test, verify, fix edge cases |

---

## Work Breakdown (Tasks)

### Task 1: Basic streaming callback
**Task ID:** T1
**Owner:** context-engineer
**Estimate:** 30 min
**Dependencies:** None
**Target Milestone:** M1

**Files/Interfaces:**
- `src/tunacode/ui/app.py` — add `_streaming_callback()` method
- `src/tunacode/ui/app.py` — modify `process_request()` call at line 214

**Acceptance Tests:**
- Callback accumulates chunks in `self._current_stream_text`
- Callback adds `active` class to `streaming_output` on first chunk
- Callback updates `streaming_output.renderable` with accumulated text
- Pass callback as `streaming_callback=self._streaming_callback`

---

### Task 2: Throttled updates
**Task ID:** T2
**Owner:** context-engineer
**Estimate:** 30 min
**Dependencies:** T1
**Target Milestone:** M2

**Files/Interfaces:**
- `src/tunacode/ui/app.py` — add `STREAM_THROTTLE_MS = 100.0` constant
- `src/tunacode/ui/app.py` — add `_last_stream_update: float` tracking

**Acceptance Tests:**
- Updates occur at most every 100ms during active streaming
- All chunks are still accumulated (none lost)
- Final update occurs immediately on stream end

---

### Task 3: Cleanup and lifecycle
**Task ID:** T3
**Owner:** context-engineer
**Estimate:** 20 min
**Dependencies:** T2
**Target Milestone:** M2

**Files/Interfaces:**
- `src/tunacode/ui/app.py` — modify finally block (line 232-233)

**Acceptance Tests:**
- `streaming_output` content is cleared in finally block
- `active` class is removed in finally block
- `_current_stream_text` is reset for next request

---

### Task 4: Test and verify
**Task ID:** T4
**Owner:** context-engineer
**Estimate:** 30 min
**Dependencies:** T3
**Target Milestone:** M3

**Acceptance Tests:**
- Run `uv run textual run src/tunacode/ui/app.py` (or equivalent)
- Send a request, verify tokens appear incrementally
- Verify final response appears in chat container
- Verify no visual glitches or flicker

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| Textual UI locks up during streaming | High | Low | Throttle to 100ms; use `self.call_later()` if needed | UI becomes unresponsive |
| Partial markdown renders poorly | Medium | High | Use plain text during streaming, markdown only at end | User sees garbled markdown |
| Streaming callback raises exception | High | Low | Wrap in try/except, log error, continue | Error in logs |

---

## Test Strategy

- **Manual test only** — no new automated tests for this feature
- Test with small model (faster tokens) and large model (slower tokens)
- Test cancellation mid-stream
- Test error during streaming (network failure)

---

## Implementation Notes

### Key Code Locations

```python
# src/tunacode/ui/app.py around line 214
self._current_request_task = asyncio.create_task(
    process_request(
        ...
        streaming_callback=None,  # <-- CHANGE THIS
        ...
    )
)

# src/tunacode/core/agents/main.py:728-748
async def _handle_message_update(self, event: Any) -> None:
    if not self.streaming_callback:
        return  # <-- Won't exit early once callback is provided
    # ... calls streaming_callback(delta)
```

### Pattern from Research

```python
STREAM_THROTTLE_MS: float = 100.0

async def streaming_callback(self, chunk: str) -> None:
    self.current_stream_text += chunk  # Always accumulate
    now = time.monotonic()
    elapsed_ms = (now - self._last_display_update) * 1000
    if elapsed_ms >= STREAM_THROTTLE_MS:
        self._last_display_update = now
        self._update_streaming_panel()
```

---

## References

- Research: `memory-bank/research/2026-02-11_00-00-00_tinyagent_streaming_reimplementation.md`
- Core streaming: `src/tunacode/core/agents/main.py:670-748`
- UI disabled: `src/tunacode/ui/app.py:214`
- Widget exists: `src/tunacode/ui/app.py:99,104`
- CSS: `src/tunacode/ui/styles/layout.tcss:68-81`
- Type definition: `src/tunacode/types/callbacks.py:70`

---

## Final Gate

**Plan Summary:**
- **Path:** `memory-bank/plan/2026-02-11_00-00-00_tinyagent_streaming_reimplementation.md`
- **Milestones:** 3 (Basic → Throttle → Test)
- **Tasks:** 4 sequential tasks
- **Estimated Total Time:** ~2 hours
- **Gates:** Manual verification only (no new automated tests)

**Next Command:**
```
/context-engineer:execute "memory-bank/plan/2026-02-11_00-00-00_tinyagent_streaming_reimplementation.md"
```
