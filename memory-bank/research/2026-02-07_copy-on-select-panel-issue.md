# Research – Copy-on-Select Panel Issue
**Date:** 2026-02-07
**Phase:** Research

## Issue Description

Copy-on-select feature (PR #371, commit 0fd3c798) works for user messages and welcome text, but does NOT work for Rich Panel objects (tool output, agent panels, error panels, etc.).

## Root Cause

**Rich Panel objects with box-drawing borders do not support Textual's mouse-based text selection mechanism.**

### Technical Explanation

Textual's `Static` widget provides `selection_updated()` hook and `text_selection` property for text selection. These work by:

1. Rendering the Rich renderable to screen cell segments
2. Building a mapping from screen coordinates to text positions
3. Using this mapping to extract selected text via `get_selection()`

**This mapping fails for Rich Panel objects because:**
- Box-drawing border characters (│─┌┐└┘) occupy cells in the rendered grid
- Panel structure (title bar, borders, padding) creates complex cell layout
- Mouse coordinates map to border/padding cells instead of content cells
- `get_selection()` returns `None` or empty text for panel cells

### Working Cases

User messages and welcome text work because they're flat renderables:
- `Text` objects from Rich library
- `Markdown` objects
- No borders, padding, or nested structure

### Failing Cases

Tool panels from `src/tunacode/ui/renderers/panels.py` fail:
```python
Panel(
    content,  # Group(header, params, separator, viewport, separator, status)
    title=f"[{border_color}]{tool_name}[/]",
    subtitle=f"[{muted_color}]{timestamp}[/]",
    border_style=Style(color=border_color),
    padding=(0, 1),
    width=frame_width,
)
```

## Key Files

### Copy-on-Select Implementation
- `src/tunacode/ui/widgets/chat.py:27-62` - `CopyOnSelectStatic` class
  - Line 38: `selection_updated()` method
  - Line 48: `_copy_current_selection()` method
  - Line 24: `_COPY_DEBOUNCE_MS = 0.15` debounce timer

### Panel Rendering
- `src/tunacode/ui/renderers/panels.py` - Rich Panel creation
  - `tool_panel()` - Basic tool panel
  - `error_panel()` - Error panel
  - `search_panel()` - Search results panel
  - `tool_panel_smart()` - Smart panel with width detection

### Application Integration
- `src/tunacode/ui/app.py:91` - `ChatContainer` instantiation
- `src/tunacode/ui/app.py:283` - `on_tool_result_display()` writes panels to chat
- `src/tunacode/ui/clipboard.py:46` - `copy_to_clipboard()` function

## Data Flow

```
User drags mouse over text
         ↓
Textual framework detects selection change
         ↓
Calls CopyOnSelectStatic.selection_updated(selection)
         ↓
Debounce timer set (150ms)
         ↓
Mouse release → timer fires
         ↓
_copy_current_selection() executes
         ↓
self.text_selection → Selection object
         ↓
self.get_selection(selection) → text, end_position
         ↓
FAILS for Panel objects (returns None)
         ↓
copy_to_clipboard(text) skipped
```

## Solution Options

### Option 1: CSS-Based Borders (Recommended)
Replace Rich Panel borders with Textual CSS styling:
- Remove Rich `Panel` wrapper
- Use CSS `border`, `background`, `padding` properties
- Content remains flat `Text`/`Markdown` renderables
- Textual's selection mechanism works correctly
- Maintains panel visual aesthetic

**Pros:** Cleanest solution, works with existing selection mechanism
**Cons:** Requires CSS changes for panel styling

### Option 2: Custom Mouse Handler
Override `_on_mouse_down` and `_on_mouse_up` in `CopyOnSelectStatic`:
- Manually calculate coordinate offsets for panel borders/padding
- Adjust mouse coordinates before mapping to content
- Preserve exact Rich Panel appearance

**Pros:** Preserves exact Panel appearance
**Cons:** Complex coordinate calculations, fragile

### Option 3: Separate Visuals from Content
Create custom widget that renders Panel visuals separately from content:
- Display Panel as visual overlay/background
- Keep selectable content as separate widget layer
- Most complex architecture

**Pros:** Full control over appearance and behavior
**Cons:** Highest complexity, may introduce other issues

## Rich Panel Usage Scope

### Files Using Rich Panel (`from rich.panel import Panel`)

| File | Panel() Calls |
|------|---------------|
| `src/tunacode/ui/renderers/panels.py` | 7 |
| `src/tunacode/ui/renderers/agent_response.py` | 2 |
| `src/tunacode/ui/renderers/search.py` | 1 |
| `src/tunacode/ui/renderers/tools/base.py` | 1 |
| `src/tunacode/ui/renderers/tools/update_file.py` | 1 |
| **Total** | **12** |

### Rich Library Overall Usage

Rich is used in 24 files across `src/` for:
- `Text` - Text formatting and styling
- `Table` - Tabular data display
- `Syntax` - Code syntax highlighting
- `Group` - Combining multiple renderables
- `Console` - Console rendering
- `Panel` - **Problematic for selection (this issue)**

**Impact:** Only the Panel wrapper is problematic. Other Rich types (Text, Table, Syntax, Group, Markdown) work fine with Textual's selection mechanism.

## Related Files

- `src/tunacode/ui/widgets/` - Widget directory
- `src/tunacode/ui/renderers/tools/` - Tool-specific renderers (11 files)
- `src/tunacode/ui/styles.py` - UI styling
- `docs/ui/nextstep_panels.md` - NeXTSTEP panel design guidelines

## References

- Textual Static Widget: https://textual.textualize.io/guide/widgets/
- Textual CHANGELOG - Text Selection: https://github.com/Textualize/textual/blob/main/CHANGELOG.md
- Rich Panel documentation: https://rich.readthedocs.io/en/stable/panel.html
