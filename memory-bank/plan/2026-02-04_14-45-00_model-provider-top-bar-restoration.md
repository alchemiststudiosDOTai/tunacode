---
title: "Model/Provider Top Bar Restoration – Plan"
phase: Plan
date: "2026-02-04 14:45:00"
owner: "claude"
parent_research: "memory-bank/research/2026-02-04_12-30-48_model-provider-top-bar-restoration.md"
git_commit_at_plan: "3a195b1b"
tags: [plan, ui, resource-bar, model-display]
---

## Goal

Restore the model/provider display to the leftmost position in the UI top bar (ResourceBar widget), where it was displayed before being removed in PR #218.

**Non-goals:**
- Removing model display from agent response panels (keep both locations)
- Changing how model names are abbreviated (reuse existing `_format_model()` if desired)
- Modifying LSP or token display behavior

## Scope & Assumptions

### In Scope
- Adding model display to ResourceBar widget (top bar)
- Restoring `STYLE_PRIMARY` import that was removed in PR #218
- Displaying model in leftmost position with proper separator

### Out of Scope
- Agent response panel changes (model stays there too)
- Model picker modal changes
- Session picker changes

### Assumptions
- ResourceBar already receives model data via `update_stats(model=...)` from app.py:370
- `STYLE_PRIMARY` is defined in styles.py and available for import
- Standard Rich `Text.assemble()` tuple list pattern: `[(text, style), ...]`
- Separator constant `RESOURCE_BAR_SEPARATOR` is already imported

## Deliverables

1. Modified `src/tunacode/ui/widgets/resource_bar.py`:
   - Import `STYLE_PRIMARY` from styles module
   - Display model name in leftmost position of top bar
   - Add separator after model name

2. Optional: Abbreviated model names using `_format_model()` helper from agent_response.py

## Readiness

### Preconditions
- Git repo at commit `3a195b1b` (already verified)
- Files exist and are readable:
  - `src/tunacode/ui/widgets/resource_bar.py`
  - `src/tunacode/ui/styles.py`
  - `src/tunacode/ui/renderers/agent_response.py` (for `_format_model()` reference)

### Required Decisions (User Must Confirm Before Coding)
1. **Model name format:** Should the top bar show abbreviated provider prefixes (ANTH/, OA/, GOOG/) like agent panels, or full model names?
2. **Color style:** Should the model use `STYLE_PRIMARY` (consistent with other UI elements) or the original "cyan" color from pre-PR #218?

## Milestones

- **M1:** Import restoration - Add `STYLE_PRIMARY` to imports
- **M2:** Display logic - Insert model into parts list at leftmost position
- **M3:** Formatting decision - Apply or skip `_format_model()` abbreviation
- **M4:** Verification - Test display with actual model names

## Work Breakdown (Tasks)

### T01: Restore STYLE_PRIMARY Import
**Owner:** claude
**Estimate:** Small
**Dependencies:** None
**Milestone:** M1

Add missing import to resource_bar.py:
```python
# Line 10-15 area, add to existing imports
from tunacode.ui.styles import STYLE_PRIMARY
```

**Acceptance Test:** Import section includes `STYLE_PRIMARY` alongside existing style imports (ERROR, MUTED, SUCCESS, WARNING).

**Files Touched:**
- `src/tunacode/ui/widgets/resource_bar.py` (line ~10-15)

---

### T02: Add Model Display to Top Bar (Leftmost Position)
**Owner:** claude
**Estimate:** Small
**Dependencies:** T01
**Milestone:** M2

Modify `_refresh_display()` method to prepend model to parts list:
```python
# Line 98, insert at beginning of parts list
parts: list[tuple[str, str]] = [
    (self._model, STYLE_PRIMARY),  # Model - leftmost
    (sep, STYLE_MUTED),             # Separator
    (circle_char, circle_color),
    (f" {remaining_pct:.0f}%", circle_color),
    (sep, STYLE_MUTED),
    (session_cost_str, STYLE_SUCCESS),
    # ... LSP conditional parts unchanged
]
```

**Acceptance Test:** Model name appears in top bar before token circle, with separator between them.

**Files Touched:**
- `src/tunacode/ui/widgets/resource_bar.py` (line ~98)

---

### T03: Apply Model Name Abbreviation (Optional - Pending User Decision)
**Owner:** claude
**Estimate:** Small
**Dependencies:** T02
**Milestone:** M3

**IF** user chooses abbreviated format: Import and use `_format_model()` helper.

Option A: Import and apply abbreviation:
```python
# Add import at top
from tunacode.ui.renderers.agent_response import _format_model

# In _refresh_display(), use abbreviated model
formatted_model = _format_model(self._model)
parts: list[tuple[str, str]] = [
    (formatted_model, STYLE_PRIMARY),
    # ...
]
```

Option B: Use full model name (skip this task).

**Acceptance Test:** Model names show abbreviated provider prefixes (ANTH/, OA/) OR full names depending on user choice.

**Files Touched:**
- `src/tunacode/ui/widgets/resource_bar.py` (import + usage)

---

### T04: Manual Visual Verification
**Owner:** user (manual testing)
**Estimate:** Small
**Dependencies:** T02 (and T03 if applicable)
**Milestone:** M4

User tests with tunacode:
1. Start application and observe top bar
2. Verify model appears leftmost with correct separator
3. Check model name format (abbreviated vs full)
4. Verify color is correct (STYLE_PRIMARY / cyan)

**Acceptance Test:** Visual confirmation matches expected design.

**Files Touched:**
- None (manual verification only)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model name too long, overflows narrow screens | Medium | Use `_format_model()` abbreviation (T03 optional) |
| STYLE_PRIMARY conflicts with existing color scheme | Low | Verified: STYLE_PRIMARY exists in styles.py and used elsewhere |
| Model already shows in agent panels, could be redundant | Low | Acceptable - user wants both locations |

## Test Strategy

- **No new automated tests required** - this is a pure UI display change
- Visual verification by user (T04) is sufficient
- Existing `update_stats(model=...)` path already tested via app.py integration

## References

- Research doc: `memory-bank/research/2026-02-04_12-30-48_model-provider-top-bar-restoration.md`
- Original implementation (pre-PR #218): commit ab1a0361
- When removed (PR #218): commit ea2ae9fb
- Current ResourceBar: `src/tunacode/ui/widgets/resource_bar.py:90-113`
- Agent response `_format_model()`: `src/tunacode/ui/renderers/agent_response.py:56-78`

## Final Gate

**Plan Output:** `memory-bank/plan/2026-02-04_14-45-00_model-provider-top-bar-restoration.md`
**Milestones:** 4 (Import, Display, Format, Verify)
**Tasks:** 4 (T01-T03 coding, T04 manual verification)
**Tasks Ready for Coding:** Yes, pending user decision on T03 (abbreviation format)

**Next Steps:**
1. User confirms: abbreviated format (T03) or full model names?
2. User confirms: `STYLE_PRIMARY` color or original "cyan"?
3. Execute: `/execute "memory-bank/plan/2026-02-04_14-45-00_model-provider-top-bar-restoration.md"`
