---
title: "Renderer Unification - Current Pattern Analysis"
phase: Plan
date: "2026-01-07T17:30:00"
owner: "Claude"
parent_plan: "memory-bank/plan/2026-01-07_16-30-00_renderer-unification.md"
tags: [plan, renderer, analysis, pattern]
---

## Current Tool Renderer Patterns (All 8)

### Uniform Function Signature

```python
def render_*(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
```

### Each Renderer Has

| Element | Purpose |
|---------|---------|
| `Data` dataclass | Structured parsed result |
| `parse_result()` | Raw string -> Data |
| `render_*()` | Data -> Rich Panel |
| `_truncate_*()` | Width/line truncation helpers |

### The 4-Zone Layout Pattern

```
┌──────────────────────────────────────────────┐
│ [bold]tool_name[/]   status info            │  ← Zone 1: Header
├──────────────────────────────────────────────┤
│ param1: value1   param2: value2              │  ← Zone 2: Params
├──────────────────────────────────────────────┤
│                                            │  ← Zone 3: Viewport
│         main content (padded)               │
│                                            │
├──────────────────────────────────────────────┤
│ info1   info2   123ms                       │  ← Zone 4: Status
└──────────────────────────────────────────────┘
```

### Zone Composition (all renderers)

```python
content = Group(
    header,
    Text("\n"),
    params,
    Text("\n"),
    separator,      # BOX_HORIZONTAL * SEPARATOR_WIDTH
    Text("\n"),
    viewport,
    Text("\n"),
    separator,
    Text("\n"),
    status,
)

return Panel(
    content,
    title=f"[color]tool_name[/] [status]",
    subtitle=f"[muted]{timestamp}[/]",
    border_style=Style(color=color),
    padding=(0, 1),
    expand=True,
    width=TOOL_PANEL_WIDTH,
)
```

### Shared Constants (from constants.py)

```python
TOOL_PANEL_WIDTH = 80
TOOL_VIEWPORT_LINES = 26
MIN_VIEWPORT_LINES = 26
MAX_PANEL_LINE_WIDTH = 200
UI_COLORS = {...}
```

### Renderer-by-Renderer Mapping

| Renderer | Data Class | Zone 1 | Zone 2 | Zone 3 | Zone 4 |
|----------|------------|--------|--------|--------|--------|
| `list_dir` | `ListDirData` | dirname, file/dir count | hidden, max, ignore | tree content | truncation, lines, ms |
| `bash` | `BashData` | command, exit status | cwd, timeout | stdout/stderr | truncation, lines, ms |
| `read_file` | `ReadFileData` | filename, line range | filepath | numbered content | total lines, more, ms |
| `update_file` | `UpdateFileData` | filename, +/ - stats | filepath | diff syntax | hunks, truncation, ms |
| `glob` | `GlobData` | pattern, file count | recursive, hidden, sort | file paths | source, truncation, ms |
| `grep` | `GrepData` | pattern, match count | strategy, case, regex | matches grouped by file | truncation, files, ms |
| `web_fetch` | `WebFetchData` | domain, line count | url, timeout | content preview | truncation, lines, ms |
| `research` | `ResearchData` | query | dirs, max_files | files, findings, recs | file/finding count, ms |

### Duplication Across All Renderers

| Element | Duplicated |
|---------|------------|
| `BOX_HORIZONTAL = "─"` | 7 times |
| `SEPARATOR_WIDTH = 52` | 7 times |
| `_truncate_line()` function | 7 times |
| Padding logic (`while len < MIN_VIEWPORT_LINES`) | 7 times |
| `Group(...separator...\n)` composition | 7 times |
| `Panel(...)` wrapper | 7 times |
| Timestamp extraction | 7 times |

### Base Class Design Implications

**Abstract methods needed:**
1. `parse_result(args, result)` -> Data | None
2. `build_header(data, duration_ms)` -> Text
3. `build_params(data)` -> Text | None
4. `build_viewport(data)` -> RenderableType | None
5. `build_status(data, duration_ms)` -> Text

**Default `render()` implements:**
- Call `parse_result()`
- Call each `build_*()`
- Compose with separators
- Wrap in Panel
- Handle None returns

**Shared helpers (to be extracted):**
- `truncate_line(text, max_width)` -> str
- `pad_to_min_height(lines, min_lines)` -> list[str]
- `build_separator(width, char)` -> Text
- `compose_4zone(header, params, viewport, status)` -> Group
- `wrap_panel(content, title, subtitle, border_color)` -> Panel

## Next: T2 Implementation

Create `base.py` with:
- `ToolRendererProtocol`
- `BaseToolRenderer` (ABC)
- No helper functions yet (T3)
- No decorator (T4)
