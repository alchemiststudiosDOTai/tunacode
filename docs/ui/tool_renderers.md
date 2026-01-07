# Tool Renderer Architecture

**Date:** 2026-01-07
**Scope:** UI / Renderers
**Status:** Canonical

## Overview

Tool renderers transform raw tool output into structured NeXTSTEP-style panels. All renderers follow a uniform 4-zone layout pattern and share common infrastructure via `BaseToolRenderer`.

**Location:** `src/tunacode/ui/renderers/tools/`

## The 4-Zone Layout

Every tool panel follows this structure:

```
┌──────────────────────────────────────────────────┐
│ [bold]tool_name[/]   status info                 │  Zone 1: Header
│ param1: value1   param2: value2                  │  Zone 2: Params
│ ──────────                                       │  Separator
│ main content                                     │  Zone 3: Viewport
│ ──────────                                       │  Separator
│ info1   info2   123ms                            │  Zone 4: Status
└──────────────────────────────────────────────────┘
  09:41:23                                           Subtitle (timestamp)
```

### Zone Responsibilities

| Zone | Purpose | Example |
|------|---------|---------|
| Header | Tool identity + result summary | `mydir   45 files  12 dirs` |
| Params | Input parameters used | `hidden: off  max: 100` |
| Viewport | Primary content (padded to min height) | Tree, diff, matches |
| Status | Truncation info, metrics, timing | `[26/100 lines]  145ms` |

## Base Classes

### BaseToolRenderer[T]

Abstract base class implementing the template method pattern. Subclasses provide tool-specific logic; the base handles composition.

```python
from tunacode.ui.renderers.tools import BaseToolRenderer, RendererConfig

class MyToolRenderer(BaseToolRenderer[MyToolData]):
    def parse_result(self, args, result) -> MyToolData | None:
        """Parse raw output into structured data."""
        ...

    def build_header(self, data, duration_ms) -> Text:
        """Zone 1: tool name + summary."""
        ...

    def build_params(self, data) -> Text | None:
        """Zone 2: input parameters."""
        ...

    def build_viewport(self, data) -> RenderableType:
        """Zone 3: main content."""
        ...

    def build_status(self, data, duration_ms) -> Text:
        """Zone 4: metrics and timing."""
        ...
```

### Optional Overrides

```python
def get_border_color(self, data) -> str:
    """Panel border color. Default: success green."""
    return self.config.warning_color if data.has_error else self.config.success_color

def get_status_text(self, data) -> str:
    """Title status text. Default: 'done'."""
    return f"exit {data.exit_code}" if data.exit_code != 0 else "done"
```

## Helper Functions

Shared utilities eliminate duplication across renderers:

```python
from tunacode.ui.renderers.tools import truncate_line, truncate_content, pad_lines

# Truncate single line with ellipsis
line = truncate_line("very long line...", max_width=60)

# Truncate multi-line content, returns (content, shown, total)
content, shown, total = truncate_content(raw_output, max_lines=10)

# Pad to minimum viewport height
lines = pad_lines(content.split("\n"), min_lines=4)
```

## Registry Pattern

Renderers self-register using the `@tool_renderer` decorator:

```python
from tunacode.ui.renderers.tools import tool_renderer

@tool_renderer("my_tool")
def render_my_tool(args, result, duration_ms=None):
    """Render my_tool output."""
    return _renderer.render(args, result, duration_ms)
```

### Lookup Functions

```python
from tunacode.ui.renderers.tools import list_renderers

# List all registered renderers
names = list_renderers()  # ["bash", "list_dir", ...]
```

## Creating a New Renderer

1. Create `src/tunacode/ui/renderers/tools/my_tool.py`
2. Define a dataclass for parsed data
3. Implement `BaseToolRenderer[MyData]`
4. Create module-level instance and render function
5. Register with `@tool_renderer`
6. Export from `__init__.py`
7. Add to `UNIFIED_RENDERERS` in `tests/test_base_renderer.py`

### Minimal Example

```python
"""Renderer for my_tool output."""

from dataclasses import dataclass
from typing import Any

from rich.console import RenderableType
from rich.text import Text

from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    pad_lines,
    tool_renderer,
    truncate_content,
)


@dataclass
class MyToolData:
    """Parsed my_tool result."""
    name: str
    content: str
    count: int


class MyToolRenderer(BaseToolRenderer[MyToolData]):
    def parse_result(self, args, result) -> MyToolData | None:
        if not result:
            return None
        return MyToolData(name="example", content=result, count=len(result.splitlines()))

    def build_header(self, data, duration_ms) -> Text:
        header = Text()
        header.append(data.name, style="bold")
        header.append(f"   {data.count} items", style="dim")
        return header

    def build_params(self, data) -> Text | None:
        return None  # No params to display

    def build_viewport(self, data) -> RenderableType:
        content, _, _ = truncate_content(data.content)
        lines = pad_lines(content.split("\n"))
        return Text("\n".join(lines))

    def build_status(self, data, duration_ms) -> Text:
        items = []
        if duration_ms:
            items.append(f"{duration_ms:.0f}ms")
        return Text("  ".join(items), style="dim")


_renderer = MyToolRenderer(RendererConfig(tool_name="my_tool"))


@tool_renderer("my_tool")
def render_my_tool(args, result, duration_ms=None) -> RenderableType | None:
    return _renderer.render(args, result, duration_ms)
```

## Constants

Defined in `tunacode.constants`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `TOOL_PANEL_WIDTH` | 60 | Panel width in characters |
| `TOOL_VIEWPORT_LINES` | 10 | Max lines before truncation |
| `MIN_VIEWPORT_LINES` | 4 | Minimum viewport height (padding) |
| `MAX_PANEL_LINE_WIDTH` | 60 | Max chars per line before truncation |

Defined in `base.py`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `BOX_HORIZONTAL` | `─` | Separator character |
| `SEPARATOR_WIDTH` | 10 | Separator line width |

## Current Renderers

| Tool | Status | Renderer Class |
|------|--------|----------------|
| `list_dir` | Unified | `ListDirRenderer` |
| `bash` | Unified | `BashRenderer` |
| `read_file` | Legacy | (function) |
| `update_file` | Legacy | (function) |
| `glob` | Legacy | (function) |
| `grep` | Legacy | (function) |
| `web_fetch` | Legacy | (function) |
| `research_codebase` | Legacy | (function) |

## Testing & Enforcement

Renderers using `BaseToolRenderer` are enforced via `tests/test_base_renderer.py`:

```python
UNIFIED_RENDERERS = {
    "list_dir": ListDirRenderer,
    "bash": BashRenderer,
}
```

Tests verify:
- Each renderer inherits from `BaseToolRenderer`
- Each renderer is registered in the registry

When migrating a renderer, add it to `UNIFIED_RENDERERS` dict.

## Verification Checklist

When creating or modifying a renderer:

- [ ] Inherits from `BaseToolRenderer`
- [ ] Uses shared helpers (no local `_truncate_line`)
- [ ] Registered with `@tool_renderer`
- [ ] Added to `UNIFIED_RENDERERS` in test file
- [ ] Exported from `__init__.py`
