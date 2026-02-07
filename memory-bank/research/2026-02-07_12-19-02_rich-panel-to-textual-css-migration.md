# Research -- Rich Panel to Textual CSS Migration

**Date:** 2026-02-07
**Owner:** agent
**Phase:** Research
**git_commit:** 1cf75e4acff953888d8c54b3ceeb787d17a973dc
**tags:** ui, rich-panel, textual-css, copy-on-select, nextstep, migration

## Goal

Map every Rich `Panel()` usage in the codebase and the surrounding rendering pipeline to prepare for replacing Rich Panels with native Textual CSS-styled widgets. This migration fixes the copy-on-select bug where Rich Panel box-drawing borders break Textual's text selection coordinate mapping.

Prior research: `memory-bank/research/2026-02-07_copy-on-select-panel-issue.md`

## Findings

### Complete Panel() Call Site Inventory (12 sites across 5 files)

| # | File | Line(s) | Function/Method | Sizing | Content Rich Types |
|---|------|---------|-----------------|---------|--------------------|
| 1 | [`renderers/panels.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/panels.py#L162) | 162-169 | `RichPanelRenderer.render_tool()` | `width=frame_width` | `Group`, `Table.grid`, `Text` |
| 2 | [`renderers/panels.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/panels.py#L213) | 213-220 | `RichPanelRenderer.render_diff_tool()` | `expand=True` | `Group`, `Table.grid`, `Text`, `Syntax` |
| 3 | [`renderers/panels.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/panels.py#L260) | 260-266 | `RichPanelRenderer.render_error()` | `expand=True` | `Group`, `Text`, `Table.grid` |
| 4 | [`renderers/panels.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/panels.py#L333) | 333-340 | `RichPanelRenderer.render_search_results()` | `expand=True` | `Group`, `Text`, `Table.grid` |
| 5 | [`renderers/panels.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/panels.py#L349) | 349-355 | `RichPanelRenderer.render_info()` | `expand=True` | `Text` or passed-in `RenderableType` |
| 6 | [`renderers/panels.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/panels.py#L361) | 361-367 | `RichPanelRenderer.render_success()` | `expand=True` | `Text` |
| 7 | [`renderers/panels.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/panels.py#L373) | 373-379 | `RichPanelRenderer.render_warning()` | `expand=True` | `Text` |
| 8 | [`renderers/agent_response.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/agent_response.py#L113) | 113-119 | `render_agent_streaming()` | `expand=True` | `Group`, `Markdown`, `Text` |
| 9 | [`renderers/agent_response.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/agent_response.py#L178) | 178-185 | `render_agent_response()` | `expand=True` | `Group`, `Markdown`, `Text` |
| 10 | [`renderers/search.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/search.py#L170) | 170-176 | `SearchDisplayRenderer.render_empty_results()` | `expand=True` | `Text` |
| 11 | [`renderers/tools/base.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/tools/base.py#L474) | 474-481 | `BaseToolRenderer.render()` | `width=frame_width` | `Group`, `Text`, + subclass viewport |
| 12 | [`renderers/tools/update_file.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/1cf75e4a/src/tunacode/ui/renderers/tools/update_file.py#L251) | 251-258 | `UpdateFileRenderer.render()` (override) | `width=frame_width` | `Group`, `Text`, `Syntax` |

### Files Importing Rich Panel

| File | Import Line |
|------|-------------|
| `src/tunacode/ui/renderers/panels.py` | Line 11: `from rich.panel import Panel` |
| `src/tunacode/ui/renderers/agent_response.py` | Line 18: `from rich.panel import Panel` |
| `src/tunacode/ui/renderers/search.py` | Line 11: `from rich.panel import Panel` |
| `src/tunacode/ui/renderers/tools/base.py` | Line 20: `from rich.panel import Panel` |
| `src/tunacode/ui/renderers/tools/update_file.py` | Line 12: `from rich.panel import Panel` |

### Universal Panel Kwargs Pattern

Every `Panel()` call in the codebase shares this exact pattern:

```python
Panel(
    content,                              # Group(*parts) or Text(...)
    title=f"[{color}]{name}[/] ...",      # Always present
    subtitle=f"[{muted}]{timestamp}[/]",  # Optional
    border_style=Style(color=color_str),  # Always Style(color=str)
    padding=(0, 1),                       # Always (0, 1) -- every single call
    width=frame_width,                    # OR expand=True (never both)
)
```

Two sizing modes:
- **Fixed width**: `width=frame_width` -- used by tool panels (sites 1, 11, 12)
- **Expand**: `expand=True` -- used by all other panels (sites 2-10)

### Tool Renderers (via BaseToolRenderer)

7 tool renderers inherit from `BaseToolRenderer` and share the single `Panel()` at `base.py:474`:

| Renderer | File | Viewport Types |
|----------|------|----------------|
| `BashRenderer` | `tools/bash.py` | `Group` of `Text`, optional `Syntax` |
| `ReadFileRenderer` | `tools/read_file.py` | `Syntax` |
| `WriteFileRenderer` | `tools/write_file.py` | `Syntax` |
| `ListDirRenderer` | `tools/list_dir.py` | `Group` of styled `Text` |
| `GrepRenderer` | `tools/grep.py` | `Group` of styled `Text` |
| `GlobRenderer` | `tools/glob.py` | `Group` of styled `Text` |
| `WebFetchRenderer` | `tools/web_fetch.py` | `Syntax` or `Text` |

**Exception**: `UpdateFileRenderer` (`tools/update_file.py`) overrides `render()` entirely to add a 5th diagnostics zone.

### Data Flow: Tool Result to Screen

```
Tool execution (core/)
    |
    v
build_tool_result_callback() [ui/repl_support.py:147]
    |  truncates result, posts ToolResultDisplay message
    v
TextualReplApp.on_tool_result_display() [app.py:283]
    |  computes max_line_width via tool_panel_max_width()
    v
tool_panel_smart(name, status, args, result, ...) [panels.py:479]
    |  routes to specialized renderer or fallback generic tool_panel()
    v
Specialized renderer.render() -> returns Panel(...)
    |
    v
ChatContainer.write(panel) [widgets/chat.py:102]
    |  creates CopyOnSelectStatic(panel)
    |  adds CSS class "chat-message" (and "expand" if expand=True)
    |  calls self.mount(widget)
    v
CopyOnSelectStatic renders Panel via Textual's Static base
    |  selection_updated() fires on mouse drag
    |  debounce 150ms -> _copy_current_selection()
    |  self.get_selection() -> FAILS for Panel (box-drawing chars)
    v
copy_to_clipboard() [clipboard.py:46] -- never reached for Panel content
```

### CopyOnSelectStatic Widget Details

Defined at `src/tunacode/ui/widgets/chat.py:27-61`:

- Extends `textual.widgets.Static`
- Constructor: `__init__(self, content: RenderableType = "")`
- `selection_updated(selection)` -- hook from Textual, sets debounce timer
- `_copy_current_selection()` -- reads `self.text_selection`, calls `self.get_selection(selection)`, copies result
- `_COPY_DEBOUNCE_MS = 0.15` (150ms debounce)
- Used exclusively within `ChatContainer.write()` at line 119

### Existing TCSS Files

| File | Purpose |
|------|---------|
| `src/tunacode/ui/styles/panels.tcss` | Panel CSS classes (already defined, currently unused by Rich Panels) |
| `src/tunacode/ui/styles/theme-nextstep.tcss` | NeXTSTEP 3D bevel border overrides |
| `src/tunacode/ui/styles/widgets.tcss` | Widget base styles |
| `src/tunacode/ui/styles/layout.tcss` | Layout structure |
| `src/tunacode/ui/styles/modals.tcss` | Modal dialog styles |

### Pre-Existing CSS Panel Classes (panels.tcss)

These CSS classes already exist but are NOT connected to any widget:

```css
.tool-panel     { border: solid $primary;   background: $surface; padding: 0 1; margin: 0 0 1 0; }
.tool-panel.running   { border: solid $accent; }
.tool-panel.completed { border: solid $success; }
.tool-panel.failed    { border: solid $error; }
.error-panel    { border: solid $error;     background: $surface; padding: 0 1; margin: 0 0 1 0; }
.error-panel.warning  { border: solid $warning; }
.error-panel.info     { border: solid $secondary; }
.search-panel   { border: solid $accent;    background: $surface; padding: 0 1; margin: 0 0 1 0; }
```

### NeXTSTEP Theme Overrides (theme-nextstep.tcss)

The NeXTSTEP theme replaces flat borders with 3D bevels:

```css
.theme-nextstep .tool-panel           { /* raised bevel: light top/left, dark bottom/right */ }
.theme-nextstep .tool-panel.running   { /* inverted bevel: dark top/left, light bottom/right */ }
.theme-nextstep .tool-panel.completed { border: solid #2a2a2a; }
.theme-nextstep .tool-panel.failed    { border: dashed #2a2a2a; }
```

### NeXTSTEP Panel Design Requirements (docs/ui/nextstep_panels.md)

Standard 4-Zone Layout that must be preserved:

```
+------------------------------------------------------------------+
|  TOOL_NAME [STATUS]                                              |  Zone 1: Header
+------------------------------------------------------------------+
|  [Arguments]                                                     |  Zone 2: Context
|  filepath: src/main.py                                           |
|                                                                  |
|  [Content]                                                       |  Zone 3: Viewport (hero)
|  (primary tool output)                                           |
|                                                                  |
|  [Footer]                                                        |  Zone 4: Status
|  145ms / 12 lines                                                |
+------------------------------------------------------------------+
   09:41 AM                                                           Subtitle
```

Rules:
- All tools must use the Standard Tool Panel layout
- Border colors reflect tool state (success=green, error=red, running=cyan)
- Title format: `"[{color}]{tool_name}[/] [{status}]"`
- Subtitle: timestamp

### Border Color Conventions

From `PANEL_STYLES` in `panels.py`:

| Panel Type | Border Color | Hex |
|-----------|-------------|-----|
| TOOL | `$primary` | #00d7d7 (cyan) |
| SUCCESS | `$success` | #4ec9b0 (green) |
| ERROR | `$error` | #f44747 (red) |
| WARNING | `$warning` | #c3e88d (yellow) |
| SEARCH | `$accent` | #ff6b9d (pink) |
| INFO | `$muted` | #808080 (gray) |

Tool-specific overrides via `get_border_color()`:
- bash: green if exit_code==0, else warning
- update_file/write_file: always success (green)
- All others: default success

### Rich Imports That Survive Panel Removal

| File | Still-Needed Imports |
|------|---------------------|
| `panels.py` | `Group`, `RenderableType`, `Style`, `Syntax`, `Table`, `Text` |
| `agent_response.py` | `Group`, `RenderableType`, `Markdown`, `Style`, `Text` |
| `search.py` | `RenderableType`, `Style`, `Text` |
| `tools/base.py` | `Group`, `RenderableType`, `Style`, `Text` |
| `tools/update_file.py` | `Group`, `RenderableType`, `Style`, `Syntax`, `Text` |

`Style` may become unnecessary if all border coloring moves to CSS. `Text`, `Group`, `RenderableType` remain essential for content construction.

## Key Patterns / Solutions Found

- **Panel kwargs are uniform**: Every call uses `padding=(0, 1)` and `border_style=Style(color=str)`. This uniformity makes batch replacement straightforward.
- **CSS classes pre-exist**: `.tool-panel`, `.error-panel`, `.search-panel` classes are already defined in `panels.tcss` with matching border/padding/background rules. They are currently orphaned.
- **NeXTSTEP theme already handles CSS panels**: `theme-nextstep.tcss` has 3D bevel overrides for `.tool-panel` variants. The theming infrastructure is ready.
- **Content is cleanly separated from wrapper**: All renderers build content as `Group(*parts)` of flat Rich renderables, then wrap in `Panel()` at the last step. Only the final `Panel()` call needs replacement.
- **Two sizing modes**: Fixed-width tool panels (`width=frame_width`) vs expanding panels (`expand=True`). CSS replacement needs both: `width: auto` with max-width for fixed, and `width: 1fr` or `width: 100%` for expand.
- **Title/subtitle must be handled**: Rich Panel renders title inside the top border and subtitle inside the bottom border. CSS panels need alternative title rendering -- likely a `Text` header line inside the widget content, styled to match.
- **Single chokepoint for tool panels**: `BaseToolRenderer.render()` at `base.py:474` handles 7/8 tool renderers. Changing that one site fixes most tool panels. Only `update_file.py` has its own `Panel()` call.
- **ChatContainer.write() is the mount point**: All panels flow through `ChatContainer.write()` -> `CopyOnSelectStatic(renderable)` -> `mount()`. This is where the renderable-to-widget boundary lives.

## Knowledge Gaps

1. **Title/subtitle rendering in CSS panels**: Rich Panel embeds title text inside the border line. Textual CSS borders do not support embedded titles. Need to determine how to render title/subtitle -- likely as styled `Text` objects prepended/appended to content `Group`.
2. **Textual border title support**: Textual widgets have `border_title` and `border_subtitle` properties. Need to verify these work with `Static` widgets and whether they interfere with text selection (they might have the same box-drawing problem).
3. **Width calculation after Panel removal**: `tool_panel_frame_width()` and `panel_widths.py` calculate widths accounting for Panel border overhead. After removing Panel, these calculations need adjustment.
4. **NeXTSTEP 3D bevel with text selection**: Need to verify that Textual CSS 3D bevels (multi-edge border styling) do not break text selection the way Rich Panel borders do.
5. **`expand=True` equivalent in CSS**: Need to confirm the correct CSS property to make a `Static` widget expand to container width vs. fixed width.
6. **Streaming agent panel update pattern**: `render_agent_streaming()` is called repeatedly during streaming. Need to understand how the streaming panel is updated (full re-render? widget replacement?) and whether CSS panels change this flow.
7. **`.claude/skills/neXTSTEP-ui/` directory is missing**: Referenced in CLAUDE.md but does not exist on disk. The PDF reference material may need to be consulted separately.

## References

- Prior research: `memory-bank/research/2026-02-07_copy-on-select-panel-issue.md`
- Panel rendering: `src/tunacode/ui/renderers/panels.py`
- Tool renderer base: `src/tunacode/ui/renderers/tools/base.py`
- Agent response renderer: `src/tunacode/ui/renderers/agent_response.py`
- Search renderer: `src/tunacode/ui/renderers/search.py`
- Update file renderer (override): `src/tunacode/ui/renderers/tools/update_file.py`
- CopyOnSelectStatic widget: `src/tunacode/ui/widgets/chat.py`
- ChatContainer: `src/tunacode/ui/widgets/chat.py`
- App integration: `src/tunacode/ui/app.py`
- Clipboard: `src/tunacode/ui/clipboard.py`
- CSS panels (orphaned): `src/tunacode/ui/styles/panels.tcss`
- NeXTSTEP theme: `src/tunacode/ui/styles/theme-nextstep.tcss`
- Panel width calculations: `src/tunacode/ui/renderers/panel_widths.py`
- NeXTSTEP panel design: `docs/ui/nextstep_panels.md`
- Style constants: `src/tunacode/ui/styles.py`
