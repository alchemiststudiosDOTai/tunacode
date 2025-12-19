# Research -- Tool Panel Size Variance

**Date:** 2025-12-19
**Owner:** agent
**Phase:** Research
**Decision:** Minimum Viewport Padding (10-26 lines)

## Goal

Investigate why tool panels still vary widely in size despite recent uniformity updates. Each tool type displays different panel heights even though they should be standardized.

## Findings

### Recent Uniformity Work (Completed)

PR #190 (merged 2025-12-19) standardized the **viewport line limit** across all renderers:
- `TOOL_VIEWPORT_LINES = 26` in `src/tunacode/constants.py:37`
- All 8 tool renderers now import and use this constant
- This ensures no tool shows more than 26 lines of primary content

**However, this only standardized the MAXIMUM, not the MINIMUM.**

### Root Cause of Size Variance

The panels vary in height because:

#### 1. Viewport Content is Variable (1 to 26 lines)

Each renderer truncates content to `TOOL_VIEWPORT_LINES` but shows fewer lines if content is smaller:

| Tool | Content Example | Viewport Lines |
|------|----------------|----------------|
| glob | 5 files found | 5 lines |
| glob | 26+ files found | 26 lines |
| bash | 1 line stdout | 1 line |
| bash | 100 lines stdout | 26 lines |
| read_file | 3 line file | 3 lines |
| read_file | 1000 line file | 26 lines |

#### 2. Fixed "Chrome" Lines Vary by Renderer

Each renderer has slightly different chrome (header/params/separators/status):

**bash.py Group structure (lines 201-213):**
```
header          (1 line)
Text("\n")      (1 line)
params          (1 line)
Text("\n")      (1 line)
separator       (1 line)
Text("\n")      (1 line)
viewport        (1-26 lines)  <-- VARIABLE
Text("\n")      (1 line)
separator       (1 line)
Text("\n")      (1 line)
status          (1 line)
```
Chrome: 10 lines, Total: 11-36 lines

**glob.py** - Same structure, 10 chrome lines

**read_file.py** - Same structure, 10 chrome lines

**update_file.py (lines 187-212)** - Has optional Zone 5:
```
header          (1 line)
Text("\n")      (1 line)
params          (1 line)
Text("\n")      (1 line)
separator       (1 line)
Text("\n")      (1 line)
diff_syntax     (1-26 lines)  <-- VARIABLE
Text("\n")      (1 line)
separator       (1 line)
Text("\n")      (1 line)
status          (1 line)
[optional diagnostics zone - adds 4+ lines when present]
```
Chrome: 10-14+ lines, Total: 11-40+ lines

#### 3. No CSS Height Enforcement

Panels use `expand=False` (width only) and no explicit height:
- `src/tunacode/ui/app.tcss` has no panel height constraints
- Rich Panel sizes based on content, not fixed dimensions

### Relevant Files

| File | Purpose |
|------|---------|
| `src/tunacode/constants.py:31-37` | Size constants (MAX_PANEL_LINES=30, TOOL_VIEWPORT_LINES=26) |
| `src/tunacode/ui/renderers/tools/bash.py:201-213` | Bash Group composition |
| `src/tunacode/ui/renderers/tools/glob.py:190-202` | Glob Group composition |
| `src/tunacode/ui/renderers/tools/read_file.py:192-204` | ReadFile Group composition |
| `src/tunacode/ui/renderers/tools/update_file.py:187-212` | UpdateFile Group composition (5-zone) |
| `src/tunacode/ui/renderers/tools/grep.py` | Grep renderer |
| `src/tunacode/ui/renderers/tools/list_dir.py` | ListDir renderer |
| `src/tunacode/ui/renderers/tools/web_fetch.py` | WebFetch renderer |
| `src/tunacode/ui/renderers/tools/research.py` | Research renderer |
| `src/tunacode/ui/app.tcss:217-234` | Panel CSS (no height rules) |

## Key Patterns / Solutions Found

### Pattern 1: Maximum Enforcement (Current)
```python
max_display = TOOL_VIEWPORT_LINES  # 26
for i, item in enumerate(items):
    if i >= max_display:
        break
    # render item
```
**Limitation:** Only caps maximum, doesn't enforce minimum.

### Pattern 2: Minimum Padding (Not Implemented)
To achieve uniform height, viewport would need padding:
```python
viewport_lines = [...actual content...]
while len(viewport_lines) < TOOL_VIEWPORT_LINES:
    viewport_lines.append("")  # pad to minimum
```

### Pattern 3: Fixed CSS Height (Not Implemented)
Alternative: enforce fixed height in CSS:
```css
.tool-panel {
    height: 38;  /* fixed lines */
}
```

## Knowledge Gaps

1. **Design intent unclear:** Should panels be exactly the same height (uniform look) or size-to-content (information density)?

2. **NeXTSTEP precedent:** Original NeXTSTEP panels varied based on content or had fixed heights?

3. **User preference:** Does the user want:
   - A: Fixed height panels (consistent but may have empty space)
   - B: Content-sized panels (dense but visually varied)

## Recommendations

### If Uniform Height is Desired:

**Option A: Viewport Padding**
- Add minimum line padding to viewport content when below `TOOL_VIEWPORT_LINES`
- Pros: Simple, contained to renderers
- Cons: Empty space when content is small

**Option B: Rich Panel Height**
- Use Rich Panel's `height` parameter
- Pros: Centralized control
- Cons: May clip content, Rich Panel height behavior varies

**Option C: CSS Fixed Height**
- Add `height: 38` (or similar) to panel CSS class
- Pros: Centralized, easy to adjust
- Cons: May not work well with Rich panels in RichLog

### Implementation Priority

1. Clarify design intent with user
2. Choose approach based on NeXTSTEP design philosophy
3. Implement consistently across all 8 renderers

---

## Decision: Minimum Viewport Padding (Recommended)

**Chosen approach:** Set a minimum viewport height (10-12 lines) while keeping max at 26.

### Rationale

| Benefit | Rationale |
|---------|-----------|
| Visual baseline | All panels share a recognizable "shape" |
| No wasted space | Only pads very small outputs |
| Information density | Large outputs still truncate at 26 |
| Simple implementation | Add padding logic to each renderer |

### Why Not Fixed Height?

Fixed height (38 lines) would mean:
- A glob returning 3 files wastes 23 lines of whitespace
- Terminal real estate is precious
- Feels "bureaucratic" rather than NeXTSTEP-clean

### Why Not Keep Current?

Current 1-26 line variance means:
- A bash "(no output)" panel is tiny
- A read_file with 26 lines is huge
- Visually jarring when mixed

### Implementation

Add a constant and padding logic:

```python
# constants.py
MIN_VIEWPORT_LINES = 10  # Baseline presence

# In each renderer's viewport section:
while len(viewport_lines) < MIN_VIEWPORT_LINES:
    viewport_lines.append("")
```

This creates a bounded range of **10-26 lines** for viewports instead of **1-26**, reducing variance by ~60%.

### Affected Files

All 8 tool renderers in `src/tunacode/ui/renderers/tools/`:
- `bash.py`
- `glob.py`
- `grep.py`
- `list_dir.py`
- `read_file.py`
- `research.py`
- `update_file.py`
- `web_fetch.py`

Plus constant addition in `src/tunacode/constants.py`.

---

## References

- `src/tunacode/constants.py` - Viewport sizing constants
- `src/tunacode/ui/renderers/tools/*.py` - All 8 tool renderers
- `memory-bank/research/2025-12-18_15-30-00_nextstep-tool-panel-audit.md` - Prior audit
- `memory-bank/research/2025-12-18_18-05-00_issue184_viewport_standardization.md` - Viewport work
- `docs/ui/nextstep_panels.md` - Design documentation
