---
title: "Tool Panel Minimum Viewport Padding - Plan"
phase: Plan
date: "2025-12-19"
owner: "agent"
parent_research: "memory-bank/research/2025-12-19_tool-panel-size-variance.md"
git_commit_at_plan: "3dd28e3"
tags: [plan, tool-panel, viewport, coding]
---

## Goal

- Implement minimum viewport padding (10 lines) across all 8 tool renderers to reduce panel size variance from 1-26 lines to 10-26 lines.

**Non-goals:**
- CSS height enforcement
- Fixed panel heights
- Changes to panel chrome structure
- Deployment or observability concerns

## Scope & Assumptions

**In scope:**
- Add `MIN_VIEWPORT_LINES = 10` constant
- Add padding logic to all 8 tool renderers
- Ensure viewport content is padded to minimum when below threshold

**Out of scope:**
- Panel chrome changes
- RichLog or scrolling behavior
- CSS modifications

**Assumptions:**
- Rich Text objects accept empty strings for padding
- Existing `TOOL_VIEWPORT_LINES = 26` max limit remains unchanged
- All renderers use similar Group composition pattern

## Deliverables

1. New constant `MIN_VIEWPORT_LINES = 10` in `src/tunacode/constants.py`
2. Padding logic in each of 8 tool renderers
3. Consistent viewport height behavior (10-26 lines)

## Readiness

- Repo at commit `3dd28e3`
- All 8 renderers already import `TOOL_VIEWPORT_LINES` from constants
- Group composition pattern documented in research

## Milestones

- **M1:** Add constant to `constants.py`
- **M2:** Implement padding in all 8 renderers
- **M3:** Verify visual consistency

## Work Breakdown (Tasks)

| ID | Task | Owner | Est | Deps | Milestone | Files |
|----|------|-------|-----|------|-----------|-------|
| T1 | Add MIN_VIEWPORT_LINES constant | agent | 5m | - | M1 | `src/tunacode/constants.py` |
| T2 | Implement padding in bash.py | agent | 10m | T1 | M2 | `src/tunacode/ui/renderers/tools/bash.py` |
| T3 | Implement padding in glob.py | agent | 10m | T1 | M2 | `src/tunacode/ui/renderers/tools/glob.py` |
| T4 | Implement padding in grep.py | agent | 10m | T1 | M2 | `src/tunacode/ui/renderers/tools/grep.py` |
| T5 | Implement padding in list_dir.py | agent | 10m | T1 | M2 | `src/tunacode/ui/renderers/tools/list_dir.py` |
| T6 | Implement padding in read_file.py | agent | 10m | T1 | M2 | `src/tunacode/ui/renderers/tools/read_file.py` |
| T7 | Implement padding in research.py | agent | 10m | T1 | M2 | `src/tunacode/ui/renderers/tools/research.py` |
| T8 | Implement padding in update_file.py | agent | 10m | T1 | M2 | `src/tunacode/ui/renderers/tools/update_file.py` |
| T9 | Implement padding in web_fetch.py | agent | 10m | T1 | M2 | `src/tunacode/ui/renderers/tools/web_fetch.py` |
| T10 | Run ruff check and verify | agent | 5m | T2-T9 | M3 | all |

### Task Details

**T1: Add MIN_VIEWPORT_LINES constant**
- Add `MIN_VIEWPORT_LINES = 10` near existing `TOOL_VIEWPORT_LINES = 26`
- Acceptance: Constant imports successfully in renderers

**T2-T9: Implement padding in each renderer**

Pattern to implement in each renderer after building viewport content:

```python
from tunacode.constants import MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES

# After building viewport_lines list, before creating Text/Group:
while len(viewport_lines) < MIN_VIEWPORT_LINES:
    viewport_lines.append("")
```

Each renderer has a viewport section that builds a list of lines. Locate that section and add padding after content is built but before it's rendered.

- Acceptance per renderer: Panel shows minimum 10 viewport lines when content is smaller

**T10: Run ruff check**
- Run `ruff check --fix .`
- Acceptance: No linting errors

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Renderer patterns vary | Medium | Research shows similar Group patterns; adapt padding to each |
| Empty string rendering | Low | Rich Text handles empty strings; fallback to space if needed |

## Test Strategy

- Manual visual verification: Run tunacode, trigger tools with small output, confirm 10-line minimum
- No new unit tests required for this cosmetic change

## References

- Research: `memory-bank/research/2025-12-19_tool-panel-size-variance.md`
- Constants: `src/tunacode/constants.py:31-37`
- Renderer patterns: `src/tunacode/ui/renderers/tools/*.py`

---

## Final Gate

- **Plan path:** `memory-bank/plan/2025-12-19_tool-panel-min-viewport.md`
- **Milestones:** 3
- **Tasks:** 10
- **Ready for coding:** Yes

**Next command:** `/ce:execute "memory-bank/plan/2025-12-19_tool-panel-min-viewport.md"`
