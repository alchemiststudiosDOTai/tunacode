# Research - Tool Panel Architecture

**Date:** 2026-01-16
**Owner:** agent
**Phase:** Research

## Goal

Map the tool panel system architecture to understand how panels are centralized, unified, and why they may appear "too big".

## Findings

### Core File Locations

| File | Purpose |
|------|---------|
| `src/tunacode/ui/renderers/panels.py` | Generic panel utilities, `tool_panel_smart()` router |
| `src/tunacode/ui/renderers/tools/base.py` | `BaseToolRenderer` with 4-zone layout pattern |
| `src/tunacode/ui/renderers/tools/*.py` | 9 individual tool renderers |
| `src/tunacode/ui/styles/panels.tcss` | Textual CSS for panel styling |
| `src/tunacode/constants.py` | Panel sizing constants |
| `src/tunacode/ui/app.py:349-357` | `on_tool_result_display()` integration point |

### Architecture Overview

```
Tool Execution
     |
     v
ToolResultDisplay Message
     |
     v
on_tool_result_display() [app.py:349]
     |
     v
tool_panel_smart() [panels.py:476]
     |
     +---> Specialized Renderer (if registered)
     |          |
     |          v
     |     BaseToolRenderer.render() [base.py:375]
     |          |
     |          v
     |     4-Zone Layout (header, params, viewport, status)
     |
     +---> Generic tool_panel() [panels.py:424] (fallback)
     |
     v
Rich Panel (expand=True)
     |
     v
RichLog.write(panel, expand=True) [app.py:357]
```

### Panel Sizing Constants (`constants.py:38-49`)

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_PANEL_LINES` | 20 | Max lines in generic panels |
| `MAX_PANEL_LINE_WIDTH` | 50 | Max chars per line |
| `TOOL_VIEWPORT_LINES` | 8 | Max lines in tool viewport (Zone 3) |
| `MIN_VIEWPORT_LINES` | 3 | Minimum viewport padding |
| `TOOL_PANEL_WIDTH` | 50 | Panel width (unused) |
| `SEPARATOR_WIDTH` | 10 | Horizontal separator width |

### Why Panels Appear "Too Big"

1. **`expand=True` everywhere** - All panels created with `expand=True`, making them fill full terminal width
2. **RichLog double-expansion** - Both `Panel(expand=True)` AND `rich_log.write(panel, expand=True)` applied
3. **Minimum padding** - `MIN_VIEWPORT_LINES=3` forces 3 empty lines even for single-line output
4. **Width mismatch** - Content truncated at 50 chars but frame expands to full width
5. **Narrow separators** - `SEPARATOR_WIDTH=10` looks tiny in expanded frame

### The 4-Zone Layout Pattern (`base.py:244-441`)

All unified tool renderers follow this template:

```
+-----------------------------------------+
| Zone 1: Header                          |
| (tool name + summary stats)             |
+-----------------------------------------+
| Zone 2: Params                          |
| (input parameters display)              |
+-----------------------------------------+
| ────────── (separator)                  |
+-----------------------------------------+
| Zone 3: Viewport                        |
| (main content, padded to min 3 lines)   |
+-----------------------------------------+
| ────────── (separator)                  |
+-----------------------------------------+
| Zone 4: Status                          |
| (metrics, truncation info, timing)      |
+-----------------------------------------+
```

### Registered Tool Renderers

**Unified Renderers (BaseToolRenderer):**
- `list_dir` - `ListDirRenderer` at `tools/list_dir.py`
- `bash` - `BashRenderer` at `tools/bash.py`

**Legacy Renderers (function-based):**
- `read_file`, `update_file`, `glob`, `grep`, `web_fetch`, `research_codebase`, `write_file`

### Renderer Registration Pattern

```python
# In tools/base.py
_renderer_registry: dict[str, RenderFunc] = {}

@tool_renderer("list_dir")
def render_list_dir(args, result, duration_ms):
    return _renderer.render(args, result, duration_ms)
```

Router at `panels.py:505-514`:
```python
renderer_map = {
    "list_dir": render_list_dir,
    "grep": render_grep,
    "glob": render_glob,
    "read_file": render_read_file,
    "update_file": render_update_file,
    "bash": render_bash,
    "web_fetch": render_web_fetch,
    "research_codebase": render_research_codebase,
}
```

### Historical Context: Slim Panel Rollback

Commit `7e0fbdd` introduced slim panels with:
- Thin rounded cyan frames
- `SLIM_PANEL_WIDTH = 70`
- New `slim_base.py` module

**Status:** Rolled back. `slim_base.py` deleted, constants orphaned.

## Key Patterns / Solutions Found

- **Centralization:** `tool_panel_smart()` in `panels.py:476` is the single routing point
- **Registry Pattern:** `@tool_renderer` decorator populates global registry
- **Template Method:** `BaseToolRenderer.render()` defines 4-zone skeleton
- **Expansion Control:** `expand=True` at both Panel and RichLog levels

## Knowledge Gaps

- Why was slim panel design rolled back?
- Is `TOOL_PANEL_WIDTH=50` intentionally unused?
- What triggered the "too big" perception (specific tools? scenarios?)

## References

- `src/tunacode/ui/renderers/panels.py` - Smart router and generic panels
- `src/tunacode/ui/renderers/tools/base.py` - BaseToolRenderer architecture
- `src/tunacode/constants.py` - All sizing constants
- `src/tunacode/ui/app.py:349-357` - Integration with RichLog
- `docs/ui/nextstep_panels.md` - Design philosophy
- `.claude/skills/neXTSTEP-ui/SKILL.md` - NeXTSTEP design guidelines
