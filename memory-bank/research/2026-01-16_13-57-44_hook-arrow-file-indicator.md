# Research - Adding Hook Arrow File Indicator to Tool Panels

**Date:** 2026-01-16
**Owner:** agent
**Phase:** Research

## Goal

Map out how to add the hook arrow (`↳`) file path indicator from the dream mockup to the current centralized tool panel rendering system.

## Dream Mockup Reference

`memory-bank/plan/assets/dream-mockup-slim-panels.webp`

Shows: `↳ tools/web_fetch.py` as a styled subtitle line beneath the tool name, visually connecting the tool to its target file.

## Findings

### Tool Renderer Architecture

The rendering system is centralized at `src/tunacode/ui/renderers/tools/`:

| File | Purpose |
|------|---------|
| `base.py` | Registry, base class, utilities |
| `read_file.py` | File reading display |
| `update_file.py` | File modification diffs |
| `write_file.py` | New file creation |
| `grep.py` | Search results |
| `glob.py` | Pattern matching results |
| `list_dir.py` | Directory listings |
| `bash.py` | Shell command output |
| `web_fetch.py` | URL fetch results |
| `research_codebase.py` | Research output |

### 4-Zone Layout Pattern

All tool panels follow this structure (defined in `base.py:1-8`):

```
Zone 1: Header     - Tool name + key stats (e.g., filename + line range)
Zone 2: Params     - Selection context (e.g., path: /full/path)
Zone 3: Viewport   - Main content with syntax highlighting
Zone 4: Status     - Metrics, truncation info, timing
```

### Current File Path Display

File paths appear in **Zone 2 (Params)** via `build_params()`:

**read_file.py:149-154:**
```python
def build_params(self, data: ReadFileData, max_line_width: int) -> Text:
    params = Text()
    params.append("path:", style="dim")
    params.append(f" {data.filepath}", style="dim bold")
    return params
```

Same pattern in `update_file.py:125-130` and `write_file.py:92-97`.

### Dream Mockup vs Current Implementation

| Aspect | Dream Mockup | Current |
|--------|--------------|---------|
| Indicator | `↳` hook arrow | `path:` label |
| Path shown | Relative (`tools/web_fetch.py`) | Full (`/root/tunacode/src/...`) |
| Position | Directly under tool name | Zone 2 params area |
| Style | Underlined filename | `dim bold` |

## Implementation Strategy

### Option A: Modify Zone 2 (Params)

Replace `path: /full/path` with `↳ relative/path`:

**Target files:**
- `src/tunacode/ui/renderers/tools/read_file.py` - `build_params()`
- `src/tunacode/ui/renderers/tools/update_file.py` - `build_params()`
- `src/tunacode/ui/renderers/tools/write_file.py` - `build_params()`

**Changes:**
1. Add constant `HOOK_ARROW = "↳"` to `constants.py`
2. Convert full path to relative (strip cwd prefix)
3. Change format from `path: {full}` to `{HOOK_ARROW} {relative}`
4. Style: arrow in dim, path in underline or bold

### Option B: Add to Zone 1 (Header) Subtitle

Add as second line in header area, more prominent:

**Target:** `base.py` - `build_header()` or panel subtitle

**Pros:** More visible, matches mockup placement
**Cons:** More invasive change to base class

### Recommended: Option A

Minimally invasive, stays within existing zone structure, easy to implement per-renderer.

## Key Patterns / Solutions Found

- **Registry pattern**: `@tool_renderer(name)` decorator auto-registers renderers
- **Template method**: `BaseToolRenderer.render()` calls abstract `build_*()` methods
- **Dataclass contracts**: Each renderer has typed `*Data` class (e.g., `ReadFileData`)
- **Width management**: `clamp_content_width()` and `truncate_line()` utilities in `base.py`

## Implementation Checklist

1. Add `HOOK_ARROW = "↳"` to `src/tunacode/constants.py`
2. Create helper in `base.py`: `def relative_path(filepath: str) -> str`
3. Update `read_file.py:build_params()` to use arrow format
4. Update `update_file.py:build_params()` to use arrow format
5. Update `write_file.py:build_params()` to use arrow format
6. Consider `web_fetch.py` for URL indicator variant

## Knowledge Gaps

- Should the arrow be the same color as the border or always dim?
- Should directory part be dim and filename bold (like glob.py does)?
- Does the underline style from mockup work in all terminals?

## References

- `src/tunacode/ui/renderers/tools/base.py` - Base renderer, registry, zones
- `src/tunacode/ui/renderers/tools/read_file.py:149-154` - Current path display
- `src/tunacode/ui/renderers/tools/update_file.py:125-130` - Current path display
- `src/tunacode/ui/renderers/tools/write_file.py:92-97` - Current path display
- `src/tunacode/constants.py` - UI constants and colors
- `memory-bank/plan/assets/dream-mockup-slim-panels.webp` - Target design
