---
title: "Token Counting, Context Window & Pricing Fixes – Plan"
phase: Plan
date: "2026-02-11T23:44:06"
owner: "claude"
parent_research: "memory-bank/research/2026-02-11_token-context-pricing-audit.md"
git_commit_at_plan: "bb5a333d"
tags: [plan, usage-metrics, cost-display, compaction, dedup]
---

## Goal

Fix three confirmed bugs in the usage metrics pipeline so that session totals are accurate and cost is visible to the user.

**Non-goals:**
- Reconciling heuristic estimation with provider-reported usage (separate effort)
- Adding per-call cost display (only session total)
- Changing the compaction threshold logic

## Scope & Assumptions

**In scope:**
1. Add dedup guard to prevent double-counting usage from `turn_end` + `message_end` events
2. Wire `session_total_usage.cost` to the resource bar UI
3. Capture compaction summary LLM usage into session totals

**Out of scope:**
- Token estimation accuracy improvements
- Resource bar redesign
- New test infrastructure

**Assumptions:**
- tinyagent emits both `message_end` and `turn_end` for every assistant message (confirmed by subagent analysis of `agent_loop.py:157,293`)
- Both events carry the same `AssistantMessage` object with identical usage dicts
- The `UsageMetrics.add()` accumulator is correct; only the call frequency is wrong

## Deliverables (DoD)

| # | Artifact | Acceptance Criteria |
|---|----------|-------------------|
| 1 | Dedup guard in `_record_usage_from_assistant_message()` | `session_total_usage` accumulates each assistant message's usage exactly once |
| 2 | Cost wiring in `_update_resource_bar()` | Resource bar displays non-zero `$X.XX` when `session_total_usage.cost > 0` |
| 3 | Compaction usage capture in `_generate_summary()` | Compaction LLM calls add their usage to `session_total_usage` |
| 4 | One test covering the dedup guard | Pytest passes, proves double-add is prevented |

## Readiness (DoR)

- [x] Research doc completed and validated against current HEAD
- [x] All three issues confirmed via codebase analysis
- [x] Test infrastructure exists (`tests/unit/core/test_openrouter_usage_metrics.py`)
- [x] `UsageMetrics` dataclass has `add()` method ready to use

## Milestones

- **M1: Dedup guard** — Prevent double-counting (highest severity)
- **M2: Cost display wiring** — One-line bridge from session to resource bar
- **M3: Compaction usage capture** — Record background LLM costs
- **M4: Test** — One integration test for dedup guard

## Work Breakdown (Tasks)

### T1: Add dedup guard to usage recording (M1)
- **Owner:** dev
- **Estimate:** Small
- **Dependencies:** None
- **Files:** `src/tunacode/core/agents/main.py`

**Approach:** Add an `_last_recorded_usage_id` field (using `id()` of the usage dict) to track the last recorded usage object. Before calling `session_total_usage.add()`, check if this usage dict has already been recorded. This works because both events carry the same `AssistantMessage` object reference.

**Acceptance Tests:**
- Calling `_record_usage_from_assistant_message()` twice with the same message dict only accumulates once
- Calling with different message dicts accumulates both
- `last_call_usage` is always updated regardless of dedup

### T2: Wire session cost to resource bar (M2)
- **Owner:** dev
- **Estimate:** Trivial
- **Dependencies:** None (can run parallel with T1)
- **Files:** `src/tunacode/ui/app.py`

**Approach:** Add `session_cost=session.usage.session_total_usage.cost` to the `update_stats()` call in `_update_resource_bar()`.

**Acceptance Tests:**
- Resource bar displays non-zero cost after API calls with cost data
- Display format remains `$X.XX`

### T3: Capture compaction summary usage (M3)
- **Owner:** dev
- **Estimate:** Small
- **Dependencies:** None (can run parallel with T1, T2)
- **Files:** `src/tunacode/core/compaction/controller.py`

**Approach:** After `final_message = await response.result()`, extract usage via `_parse_openrouter_usage()` (imported from `core.agents.main`) and accumulate into session totals. The controller already has access to `self._state_manager.session`. Import the parser function; keep it DRY.

**Alternative:** Pass a usage callback into the controller at construction time to avoid a direct import from `core.agents.main`. This keeps the dependency direction clean (controller should not import from agents).

**Preferred:** Callback approach — controller accepts an optional `on_usage: Callable[[dict], None]` callback, main agent passes its `_record_usage_from_assistant_message` bound method. This respects layer boundaries.

**Acceptance Tests:**
- After compaction, `session_total_usage` reflects the summary LLM call's tokens
- No import from `core.agents.main` into `core.compaction.controller`

### T4: Write dedup guard test (M4)
- **Owner:** dev
- **Estimate:** Trivial
- **Dependencies:** T1
- **Files:** `tests/unit/core/test_openrouter_usage_metrics.py`

**Acceptance Tests:**
- Test creates a mock message with usage, calls recording twice, asserts single accumulation
- Test creates two different messages, calls recording for each, asserts both accumulated

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| `id()` comparison fails if tinyagent copies the dict between events | Dedup doesn't work | Low (confirmed same object ref) | Fall back to content hash of usage dict | Usage still doubles after fix |
| Callback wiring breaks compaction isolation | Architecture regression | Medium | Keep callback optional with `None` default | grimp check fails |
| Cost value is 0.0 from some providers | Display shows $0.00 even after fix | Medium (provider-dependent) | Not a bug in our code; document | User reports $0.00 with provider X |

## Test Strategy

- ONE new test in `tests/unit/core/test_openrouter_usage_metrics.py` covering the dedup guard (T4)
- Existing parser tests (6 tests, all passing) cover cost parsing correctness
- Manual verification of cost display via resource bar after wiring

## References

- Research: `memory-bank/research/2026-02-11_token-context-pricing-audit.md`
- Debug history: `.claude/debug_history/2026-02-11-rust-usage-shape-throughput-missing.md`
- Dual recording rationale: commit `bb5a333d`
- `UsageMetrics.add()`: `src/tunacode/types/canonical.py:200-205`
- `_parse_openrouter_usage()`: `src/tunacode/core/agents/main.py:178-216`

## Drift Detected

No drift — research doc references `bb5a333d` which is current HEAD. All file locations and line numbers verified by subagent analysis against live code.

## Tickets Created (4 of 5 max)

| Ticket ID | Title | Priority | Status | Milestone |
|-----------|-------|----------|--------|-----------|
| tun-de11 | Add dedup guard to prevent double-counting usage metrics | P1 | open | M1 |
| tun-232d | Wire session cost to resource bar display | P2 | open | M2 |
| tun-8e9a | Capture compaction summary LLM usage into session totals | P2 | open | M3 |
| tun-272e | Write dedup guard unit test | P2 | open | M4 |

## Dependencies

- `tun-272e` (dedup test) depends on `tun-de11` (dedup guard implementation)
- `tun-de11`, `tun-232d`, `tun-8e9a` are independent and can run in parallel
