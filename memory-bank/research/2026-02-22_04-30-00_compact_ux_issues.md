# Research – /compact Command UX Issues

**Date:** 2026-02-22
**Owner:** context-engineer:research
**Phase:** Research

## Goal
Document the 6 distinct UX issues with the `/compact` command, all stemming from an architectural mismatch between the ResourceBar and context panel. Focus on understanding root causes and identifying relevant code locations.

## Findings

### Root Cause
ResourceBar and context panel are **mutually exclusive** via CSS `display: none`, but "Compacting..." status renders **exclusively** in the ResourceBar. The context panel has no compaction awareness at all.

### Issue Details (Ranked by Severity)

#### P0: No feedback when context panel is open
**Problem:** "Compacting..." renders only in ResourceBar, which is `display: none` when `ctrl+e` panel is visible.

**Impact:** Users see absolutely nothing happen when they run `/compact` with panel open.

**Relevant Code:**
- `src/tunacode/ui/styles/layout.tcss` (lines 33-35, 80-82) — CSS mutual exclusion rules
- `src/tunacode/ui/app.py` (lines 419-428) — `_set_context_panel_visibility()` toggles `.hidden` class on both `#context-rail` and `ResourceBar`
- `src/tunacode/ui/widgets/resource_bar.py` (lines 127-129) — "Compacting..." label rendering

---

#### P1: No immediate visual response
**Problem:** Nothing happens until controller internally fires `callback(True)` — delay between typing `/compact` and seeing anything.

**Impact:** Users wonder if the command was received.

**Relevant Code:**
- `src/tunacode/ui/commands/compact.py` (lines 57-62) — `await controller.force_compact()` blocks before callback fires
- `src/tunacode/ui/app.py` (lines 531-532) — `_update_compaction_status()` receives status only after controller starts

---

#### P2: No error feedback on exception
**Problem:** `finally` clears status but no toast is shown if `force_compact()` throws.

**Impact:** Silent failures leave users confused.

**Relevant Code:**
- `src/tunacode/ui/commands/compact.py` (lines 63-66) — `finally` block clears status without checking for exceptions
- `src/tunacode/core/compaction/controller.py` (lines 176-191) — `force_compact()` may raise exceptions

---

#### P3: No chat container record
**Problem:** Compaction leaves zero trace in the conversation (unlike `/update` which writes progress to chat).

**Impact:** No audit trail of what was compacted.

**Relevant Code:**
- `src/tunacode/ui/commands/compact.py` (lines 87-92) — Only uses `app.notify()` for completion
- `src/tunacode/ui/commands/update.py` (lines 82, 91, 94, 108, 122) — Pattern: `app.chat_container.write()` for progress

---

#### P4: No viewport state feedback
**Problem:** Agent requests get `#viewport.streaming` CSS class; `/compact` has nothing — UI looks idle.

**Impact:** No visual differentiation between idle and compacting states.

**Relevant Code:**
- `src/tunacode/ui/styles/layout.tcss` (lines 131-138) — `#viewport.streaming` styling
- `src/tunacode/ui/app.py` (lines 238, 272) — Streaming class toggling during agent requests
- `src/tunacode/ui/commands/compact.py` — No viewport state changes during compaction

---

#### P5: Ephemeral toast notifications
**Problem:** Results auto-dismiss and are never logged.

**Impact:** Users can't review what happened.

**Relevant Code:**
- `src/tunacode/ui/commands/compact.py` (lines 78-81, 87-92) — Uses `app.notify()` which auto-dismisses
- `app.chat_container.write()` would persist in conversation history

## Key Patterns / Solutions Found

### Pattern: Command Progress in Chat Container
**File:** `src/tunacode/ui/commands/update.py`
**Usage:** Writes progress updates to `app.chat_container.write()` for persistent audit trail.

### Pattern: Viewport State CSS Classes
**File:** `src/tunacode/ui/styles/layout.tcss`
**Usage:** `#viewport.streaming` and `#viewport.paused` provide visual state feedback.

### Pattern: Status Callback Architecture
**File:** `src/tunacode/core/compaction/controller.py` (lines 113-123, 300-308)
**Usage:** Controller uses `CompactionStatusCallback` to signal start/end events.

## Knowledge Gaps
- How should the context panel display compaction status? (New field? Existing field modification?)
- Should `/compact` support cancellation mid-operation?
- What visual treatment should viewport have during compaction? (Similar to streaming or different?)

## References

### Primary Files
| File | Purpose |
|------|---------|
| `src/tunacode/ui/commands/compact.py` | Main command implementation with all 6 issues |
| `src/tunacode/ui/widgets/resource_bar.py` | ResourceBar widget showing "Compacting..." |
| `src/tunacode/ui/context_panel.py` | Context panel builder (no compaction awareness) |
| `src/tunacode/ui/app.py` | App-level visibility toggling and callbacks |
| `src/tunacode/ui/styles/layout.tcss` | CSS mutual exclusion rules |

### GitHub Permalinks (commit: `e67df235`)
- [compact.py command](https://github.com/alchemiststudiosDOTai/tunacode/blob/e67df235/src/tunacode/ui/commands/compact.py)
- [resource_bar.py widget](https://github.com/alchemiststudiosDOTai/tunacode/blob/e67df235/src/tunacode/ui/widgets/resource_bar.py)
- [context_panel.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e67df235/src/tunacode/ui/context_panel.py)
- [app.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e67df235/src/tunacode/ui/app.py)
- [layout.tcss](https://github.com/alchemiststudiosDOTai/tunacode/blob/e67df235/src/tunacode/ui/styles/layout.tcss)
- [compaction controller.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e67df235/src/tunacode/core/compaction/controller.py)
- [update.py (reference pattern)](https://github.com/alchemiststudiosDOTai/tunacode/blob/e67df235/src/tunacode/ui/commands/update.py)

## Research Summary

The `/compact` command UX issues stem from a **single architectural limitation**: compaction status is displayed exclusively in the ResourceBar, but the ResourceBar is hidden when the context panel is visible (they're mutually exclusive via CSS). This creates a P0 bug where users with the context panel open receive zero feedback.

**Recommended fix approach:**
1. Add compaction status to the context panel (new or existing field)
2. Add viewport CSS state for compaction (similar to `#viewport.streaming`)
3. Add chat container progress messages (like `/update` command)
4. Fix exception handling to show error toasts

All fixes should leverage the existing `CompactionStatusCallback` architecture in the controller.
