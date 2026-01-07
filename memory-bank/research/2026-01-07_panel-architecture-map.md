# Research - Panel Architecture Map

**Date:** 2026-01-07
**Owner:** Claude
**Phase:** Research

## Goal

Map all panels, panes, and related UI components in the tunacode TUI to enable future unification efforts.

## Findings

### Panel System Overview

Panels in TunaCode are **Rich library `Panel` objects** rendered into a Textual `RichLog` widget. They are NOT Textual widgets themselves. The architecture uses a renderer-based pattern where factory functions create Rich objects that get written to the log.

### Panel Type Enum

Located at `src/tunacode/ui/renderers/panels.py:26-32`:

| Type | Value | Purpose |
|------|-------|---------|
| `TOOL` | "tool" | Tool execution results |
| `ERROR` | "error" | Error messages |
| `SEARCH` | "search" | Search results |
| `INFO` | "info" | Informational messages |
| `SUCCESS` | "success" | Success notifications |
| `WARNING` | "warning" | Warning messages |

### Core Panel Files

| File | Purpose |
|------|---------|
| `src/tunacode/ui/renderers/panels.py` | Main `RichPanelRenderer` class with factory methods |
| `src/tunacode/ui/renderers/search.py` | Search-specific panels (`file_search_panel`, `code_search_panel`) |
| `src/tunacode/ui/renderers/errors.py` | Error panel rendering with severity mapping |
| `src/tunacode/ui/renderers/__init__.py` | Public exports |

### Tool-Specific Renderers (8 total)

Located in `src/tunacode/ui/renderers/tools/`:

| Renderer | File | Tool |
|----------|------|------|
| `render_bash` | `bash.py` | Bash command output |
| `render_glob` | `glob.py` | File glob results |
| `render_grep` | `grep.py` | Grep search results |
| `render_list_dir` | `list_dir.py` | Directory listings |
| `render_read_file` | `read_file.py` | File content display |
| `render_update_file` | `update_file.py` | File diff with diagnostics |
| `render_web_fetch` | `web_fetch.py` | Web content fetching |
| `render_research_codebase` | `research.py` | Codebase research results |

All follow the **4-zone NeXTSTEP layout**:
1. **Header**: Tool name + status indicator
2. **Selection context**: Parameters/path info
3. **Primary viewport**: Main content (26 lines max)
4. **Status**: Duration, truncation info

### RichPanelRenderer Methods

Located at `src/tunacode/ui/renderers/panels.py:100-373`:

| Method | Lines | Returns |
|--------|-------|---------|
| `render_tool()` | 101-157 | Tool execution panel |
| `render_diff_tool()` | 159-209 | Diff with syntax highlighting |
| `render_error()` | 211-256 | Error panel with recovery |
| `render_search_results()` | 258-331 | Paginated search |
| `render_info()` | 333-347 | Generic info |
| `render_success()` | 349-360 | Success notification |
| `render_warning()` | 362-373 | Warning notification |

### Convenience Functions

Located at `src/tunacode/ui/renderers/panels.py:432-550`:

| Function | Line | Purpose |
|----------|------|---------|
| `tool_panel()` | 432 | Shortcut for tool panels |
| `error_panel()` | 450 | Shortcut for error panels |
| `search_panel()` | 467 | Shortcut for search panels |
| `tool_panel_smart()` | 484 | Routes to specialized renderers |

### Data Classes

Located at `src/tunacode/ui/renderers/panels.py:69-97`:

```python
@dataclass
class ToolDisplayData:
    tool_name: str
    status: str
    arguments: dict[str, Any]
    result: str | None = None
    duration_ms: float | None = None
    timestamp: str | None = None

@dataclass
class ErrorDisplayData:
    error_type: str
    message: str
    suggested_fix: str | None = None
    recovery_commands: list[str] | None = None
    context: str | None = None
    severity: str = "error"

@dataclass
class SearchResultData:
    query: str
    results: list[dict[str, Any]]
    total_count: int
    current_page: int = 1
    page_size: int = 20
    search_time_ms: float | None = None
    source: str = "unknown"
```

### Non-Panel Widgets (Textual Widgets)

Located in `src/tunacode/ui/widgets/`:

| Widget | Base | File | Purpose |
|--------|------|------|---------|
| `Editor` | `Input` | `editor.py:27` | Multi-line editor |
| `StatusBar` | `Horizontal` | `status_bar.py:20` | 3-zone status |
| `ResourceBar` | `Static` | `resource_bar.py:56` | Token/cost/model |
| `CommandAutoComplete` | `AutoComplete` | `command_autocomplete.py:16` | Slash commands |
| `FileAutoComplete` | `AutoComplete` | `file_autocomplete.py:11` | @ file mentions |

### Screens (Modal Screens)

Located in `src/tunacode/ui/screens/`:

| Screen | Base | Purpose |
|--------|------|---------|
| `SetupScreen` | `Screen[bool]` | First-time config |
| `ProviderPickerScreen` | `Screen[str \| None]` | Provider selection |
| `ModelPickerScreen` | `Screen[str \| None]` | Model selection |
| `SessionPickerScreen` | `Screen` | Session restore |
| `ThemePickerScreen` | `Screen` | Theme selection |
| `UpdateConfirmScreen` | `Screen` | Update confirmation |

### CSS Styling

| File | Purpose |
|------|---------|
| `src/tunacode/ui/styles/panels.tcss` | Base panel styles |
| `src/tunacode/ui/styles/theme-nextstep.tcss` | NeXTSTEP theme overrides |

CSS classes: `.tool-panel`, `.error-panel`, `.search-panel`
States: `.running`, `.completed`, `.failed`, `.warning`, `.info`

### Constants

From `src/tunacode/constants.py`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_PANEL_LINES` | 30 | Max lines in panel |
| `MAX_PANEL_LINE_WIDTH` | 200 | Max chars per line |
| `TOOL_VIEWPORT_LINES` | 26 | Lines for content |
| `TOOL_PANEL_WIDTH` | 80 | Fixed panel width |

### Data Flow

1. Tool executes, agent receives result
2. Callback posts `ToolResultDisplay` message (`ui/widgets/messages.py:29-46`)
3. App handler `on_tool_result_display()` at `app.py:342`
4. `tool_panel_smart()` routes to specialized renderer
5. Renderer builds Rich `Panel` object
6. Panel written to `RichLog` via `self.rich_log.write(panel)`

### Routing Map

From `src/tunacode/ui/renderers/panels.py:499-522`:

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

Unknown tools fall back to generic `tool_panel()`.

## Key Patterns / Solutions Found

| Pattern | Description |
|---------|-------------|
| **Factory Pattern** | `RichPanelRenderer` and `tool_panel_smart()` as factories |
| **Composition** | No inheritance; Rich objects composed by renderers |
| **4-Zone Layout** | All tool renderers follow NeXTSTEP zones |
| **Message Passing** | Textual `Message` for async communication |
| **Routing** | Dictionary mapping tool names to renderers |

## Issues for Unification

1. **No Panel Base Class**: Panels are ad-hoc Rich objects, no shared interface
2. **Inconsistent Data Classes**: Only 3 data classes, some renderers use raw dicts
3. **Manual Router**: New tools require manual addition to `renderer_map`
4. **Mixed Concerns**: `panels.py` contains both base renderer and routing logic
5. **No Registration**: No auto-discovery of tool renderers
6. **Hardcoded Constants**: Panel width/height scattered vs centralized

## Unification Opportunities

1. **Abstract Panel Protocol**: Define a `PanelProtocol` for all panel types
2. **Auto-Registration**: Decorator-based tool renderer registration
3. **Unified Data Model**: Single `PanelData` base class with typed variants
4. **Separate Router**: Extract routing to dedicated module
5. **Configuration**: Centralize panel dimensions in config

## References

- `src/tunacode/ui/renderers/panels.py` - Core panel system
- `src/tunacode/ui/renderers/tools/` - Tool-specific renderers (8 files)
- `src/tunacode/ui/renderers/errors.py` - Error rendering
- `src/tunacode/ui/renderers/search.py` - Search panels
- `src/tunacode/ui/styles/panels.tcss` - Panel CSS
- `src/tunacode/ui/widgets/messages.py` - Message classes
- `src/tunacode/constants.py` - Panel constants
- `docs/ui/nextstep_panels.md` - Design documentation
