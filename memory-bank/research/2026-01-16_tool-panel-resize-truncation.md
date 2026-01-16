# Research – Tool Panel Resize Truncation Issue

**Date:** 2026-01-16
**Owner:** Claude
**Phase:** Research

## Goal

Understand why tool panel content stays truncated after terminal resize, even though the panel box expands correctly.

## Findings

### Root Cause: Baked vs Dynamic Content

Content is **baked** (pre-truncated) at render time, not computed dynamically on resize:

1. `tool_panel_max_width()` calculates width once when tool result arrives
2. `truncate_content()` and `truncate_line()` permanently cut the text
3. Panel is created with `expand=True` which expands the **border**, not the content
4. The truncated string is stored - no reference to original full content

### Critical Code Flow

```
Tool completes → on_tool_result_display() → tool_panel_max_width() [ONCE]
                                                   ↓
                                          tool_panel_smart()
                                                   ↓
                                          build_viewport() → truncate_content() [PERMANENT]
                                                   ↓
                                          Syntax/Text objects created with truncated text
                                                   ↓
                                          Panel(content, expand=True) → RichLog.write()
```

### Relevant Files & Why They Matter

- `src/tunacode/ui/app.py:364-379` → `tool_panel_max_width()` calculates width once at render time
- `src/tunacode/ui/renderers/tools/base.py:36-48` → `truncate_line()` permanently cuts lines
- `src/tunacode/ui/renderers/tools/base.py:51-75` → `truncate_content()` permanently cuts vertically + horizontally
- `src/tunacode/ui/renderers/tools/base.py:471-478` → Panel created with `expand=True` (border only)
- `src/tunacode/ui/renderers/panels.py:489-538` → `tool_panel_smart()` routes to renderers

### Width Calculation Details (app.py:364-379)

```python
def tool_panel_max_width(self) -> int:
    width_candidates = [
        self.rich_log.scrollable_content_region.width,  # Most specific
        self.rich_log.content_region.width,
        self.rich_log.size.width,
        self.query_one("#viewport").size.width,
        self.size.width,                                # Fallback
    ]
    usable_widths = [width for width in width_candidates if width > 0]
    content_width = min(usable_widths)  # Uses MINIMUM of all
    available_width = content_width - TOOL_PANEL_HORIZONTAL_INSET  # -8 chars
    return max(MIN_TOOL_PANEL_LINE_WIDTH, available_width)  # Floor: 4 chars
```

**Key Insight:** Uses `min()` of all width sources - if ANY region is small, content is truncated to that.

### Truncation Mechanics (base.py)

**Line truncation (36-48):**
```python
def truncate_line(line: str, max_width: int) -> str:
    if len(line) > max_width:
        return line[: max_width - 3] + "..."  # Adds ellipsis
    return line
```

**Content truncation (51-75):**
```python
def truncate_content(content: str, max_lines: int = TOOL_VIEWPORT_LINES, *, max_width: int):
    lines = content.splitlines()
    truncated = [truncate_line(line, max_width) for line in lines[:max_lines]]
    return "\n".join(truncated), len(truncated), len(lines)
```

The ellipsis (`...`) is **baked into the string**. There's no way to recover the original content.

### Panel Creation (base.py:471-478)

```python
return Panel(
    content,       # Already truncated!
    title=...,
    expand=True,   # Only expands the BORDER, not content
    padding=(0, 1),
)
```

`expand=True` tells Rich to make the panel **border** fill available width. The content inside is just a string that was already cut.

## Key Patterns / Solutions Found

### Option 1: Store Full Content, Re-render on Resize
- Store original untruncated content with each panel
- Listen for terminal resize events
- Re-render all visible panels with new width
- **Complexity:** High - requires refactoring RichLog, tracking panel metadata

### Option 2: Remove Pre-truncation, Use Rich Word Wrap
- Don't call `truncate_line()` horizontally
- Let Rich's `word_wrap=True` handle line wrapping dynamically
- Keep vertical truncation (`TOOL_VIEWPORT_LINES = 8`)
- **Complexity:** Medium - may affect layout consistency, needs testing

### Option 3: Accept Current Behavior (Document It)
- Panels reflect state at render time
- Users can re-run tools if they resize terminal
- **Complexity:** Low - just documentation

### Option 4: Use `min()` Width Bug Fix
- The width calculation uses `min()` of all sources
- If `scrollable_content_region.width` is stuck at a small value, it clamps everything
- **Investigation needed:** Why is any width source staying small after resize?

## Knowledge Gaps

1. **Does Textual update region widths on resize?** - Need to verify if `scrollable_content_region.width` updates when terminal resizes
2. **Is there a resize event handler?** - Could we hook into terminal resize to re-query widths?
3. **Why store truncated text?** - Original design rationale unknown, may have been intentional for performance

## Behavioral Summary

| Terminal Action | Panel Border | Panel Content |
|-----------------|--------------|---------------|
| Initial render (small) | Fits small width | Truncated to small width |
| Expand terminal | Expands to new width | **Still truncated** (baked) |
| Shrink terminal | Shrinks | Still shows same truncated text |

## References

- `src/tunacode/ui/app.py` - Width calculation, panel display
- `src/tunacode/ui/renderers/tools/base.py` - Truncation functions, Panel creation
- `src/tunacode/ui/renderers/panels.py` - Panel routing
- `src/tunacode/constants.py` - `MIN_TOOL_PANEL_LINE_WIDTH=4`, `TOOL_PANEL_HORIZONTAL_INSET=8`
- Screenshot: `latesttools.png` - Visual evidence of the issue
