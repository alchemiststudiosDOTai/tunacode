---
title: "Ticket Execution Log"
phase: Execute
date: "2026-02-12T06:00:00Z"
owner: "claude"
start_commit: "bb5a333d"
tickets_planned: [tun-de11, tun-232d, tun-8e9a, tun-272e]
---

## Pre-Flight
- Branch: fix/usage-metrics-dedup-cost-compaction
- Rollback point: bb5a333d
- Tickets to execute: tun-de11, tun-232d, tun-8e9a, tun-272e

---

## Ticket: tun-de11 - Add dedup guard to prevent double-counting usage metrics

**Status:** Closed
**Commit:** `b73d4a16`

### Work Done
- Added `last_recorded_usage_id` field to `_TinyAgentStreamState`
- Added `id(raw_usage)` dedup check in `_record_usage_from_assistant_message()`
- Both callers (`turn_end`, `message_end`) now pass `stream_state=state`
- `last_call_usage` always updated; only `session_total_usage.add()` is deduped
- Files: `src/tunacode/core/agents/main.py`

### Quality Gates
- Tests: pass (6/6)
- Lint: pass (ruff)

---

## Ticket: tun-232d - Wire session cost to resource bar display

**Status:** Closed
**Commit:** `5c741da0`

### Work Done
- Added `session_cost=session.usage.session_total_usage.cost` kwarg to `update_stats()` call
- Files: `src/tunacode/ui/app.py`

### Quality Gates
- Tests: pass (6/6)
- Lint: pass (ruff)

---

## Ticket: tun-8e9a - Capture compaction summary LLM usage into session totals

**Status:** Closed
**Commit:** `e1557084`

### Work Done
- Added `_on_usage` callback field to `CompactionController`
- Added `set_usage_callback()` method
- Added `_emit_usage()` to extract and forward usage from `_generate_summary()`
- Added `_record_compaction_usage()` to `RequestOrchestrator` as the callback
- Wired via `_configure_compaction_callbacks()`
- No import from `core.agents.main` into `core.compaction.controller`
- Files: `src/tunacode/core/compaction/controller.py`, `src/tunacode/core/agents/main.py`

### Quality Gates
- Tests: pass (6/6)
- Lint: pass (ruff)

---

## Ticket: tun-272e - Write dedup guard unit test

**Status:** Closed
**Commit:** `104f9c5d`

### Work Done
- `test_dedup_guard_prevents_double_counting_same_usage_dict`: same dict twice -> single accumulation
- `test_dedup_guard_accumulates_different_usage_dicts`: different dicts -> both accumulated
- Files: `tests/unit/core/test_openrouter_usage_metrics.py`

### Quality Gates
- Tests: pass (8/8)
- Lint: pass (ruff)

---

# Execution Summary

**Branch:** fix/usage-metrics-dedup-cost-compaction
**Start commit:** bb5a333d

## Commits
| Commit | Ticket | Title |
|--------|--------|-------|
| b73d4a16 | tun-de11 | Add dedup guard to prevent double-counting usage metrics |
| 5c741da0 | tun-232d | Wire session cost to resource bar display |
| e1557084 | tun-8e9a | Capture compaction summary LLM usage into session totals |
| 104f9c5d | tun-272e | Add dedup guard unit tests for usage recording |

## Tickets Executed
| Ticket ID | Title | Status | Commit |
|-----------|-------|--------|--------|
| tun-de11 | Add dedup guard | closed | b73d4a16 |
| tun-232d | Wire session cost | closed | 5c741da0 |
| tun-8e9a | Compaction usage capture | closed | e1557084 |
| tun-272e | Dedup guard test | closed | 104f9c5d |

## Quality Summary
- Total tests: 8 (6 existing + 2 new)
- All gates passed: Yes
- End commit: 104f9c5d
- All tickets closed: Yes
- Rollback needed: No
