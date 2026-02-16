# Research -- Diff Rendering Pipeline

**Date:** 2026-02-16
**Phase:** Research

## Data Flow (End-to-End)

```
update_file() tool
  -> difflib.unified_diff() generates plain string
  -> ToolResultCallback posts ToolResultDisplay message
  -> app.on_tool_result_display() calls tool_panel_smart()
  -> tool_panel_smart() routes to render_update_file()
  -> UpdateFileRenderer.parse_result() extracts UpdateFileData
  -> UpdateFileRenderer.render() builds 4-zone Rich Group
  -> ChatContainer.write() wraps in CopyOnSelectStatic widget
  -> SelectableRichVisual renders Rich -> Textual Strips
```

## Key Files (in flow order)

| Step | File | Line | What |
|------|------|------|------|
| 1 | `src/tunacode/tools/update_file.py` | L15 | `update_file()` tool function |
| 2 | `src/tunacode/tools/update_file.py` | L55 | `difflib.unified_diff()` call |
| 3 | `src/tunacode/tools/update_file.py` | L64 | Result string assembly: `"File '...' updated.\n\n{diff_text}"` |
| 4 | `src/tunacode/tools/update_file.py` | L66 | `maybe_prepend_lsp_diagnostics()` injection |
| 5 | `src/tunacode/core/agents/main.py` | -- | `_handle_stream_tool_execution_end()` invokes callback |
| 6 | `src/tunacode/ui/repl_support.py` | L166 | `build_tool_result_callback` posts `ToolResultDisplay` |
| 7 | `src/tunacode/ui/widgets/messages.py` | L30 | `ToolResultDisplay` message class |
| 8 | `src/tunacode/ui/app.py` | L349 | `on_tool_result_display()` handler |
| 9 | `src/tunacode/ui/renderers/panels.py` | L477 | `tool_panel_smart()` router |
| 10 | `src/tunacode/ui/renderers/panels.py` | L504-512 | Hardcoded `renderer_map` dict (not using registry) |
| 11 | `src/tunacode/ui/renderers/tools/update_file.py` | L257 | `render_update_file()` entry point |
| 12 | `src/tunacode/ui/renderers/tools/update_file.py` | L45-109 | `parse_result()` string -> `UpdateFileData` |
| 13 | `src/tunacode/ui/renderers/tools/update_file.py` | L131-142 | `build_viewport()` creates `Syntax("diff", theme="monokai")` |
| 14 | `src/tunacode/ui/renderers/tools/update_file.py` | L177-250 | `render()` composes 4-zone Group |
| 15 | `src/tunacode/ui/widgets/chat.py` | L307-337 | `ChatContainer.write()` wraps in `CopyOnSelectStatic` |

## Structure

### Tool Layer
- `src/tunacode/tools/update_file.py` -- Performs file replacement, generates unified diff via `difflib.unified_diff()`, returns plain string
- `src/tunacode/tools/utils/text_match.py` -- `replace()` function with fuzzy matching (Levenshtein fallback)

### Callback Bridge
- `src/tunacode/core/agents/main.py` -- `RequestOrchestrator` handles tinyagent stream events, invokes `tool_result_callback`
- `src/tunacode/ui/repl_support.py` -- `build_tool_result_callback()` creates callback that posts `ToolResultDisplay` Textual message

### Renderer Layer
- `src/tunacode/ui/renderers/panels.py` -- `tool_panel_smart()` routes to renderers; uses hardcoded `renderer_map` (NOT registry)
- `src/tunacode/ui/renderers/tools/base.py` -- `BaseToolRenderer[T]` template method pattern; `_renderer_registry` dict; `@tool_renderer` decorator
- `src/tunacode/ui/renderers/tools/update_file.py` -- `UpdateFileRenderer(BaseToolRenderer[UpdateFileData])` with 4-zone layout
- `src/tunacode/ui/renderers/tools/diagnostics.py` -- Parses `<file_diagnostics>` XML blocks, renders inline

### Widget Layer
- `src/tunacode/ui/widgets/chat.py` -- `ChatContainer.write()` creates `CopyOnSelectStatic` widget; `SelectableRichVisual` bridges Rich -> Textual

## Diff Generation Details

```python
# src/tunacode/tools/update_file.py:54-62
diff_lines = list(
    difflib.unified_diff(
        original.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
    )
)
diff_text = "".join(diff_lines)
```

- Uses `keepends=True` to preserve line endings
- Git-style `a/` and `b/` prefixes on file paths
- Full context (no `n=` parameter, so default 3 context lines)

## Result String Format

```
File 'path/to/file.py' updated successfully.

--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,5 +10,7 @@
 context line
-removed line
+added line
 context line
```

Optional LSP diagnostics block prepended:
```xml
<file_diagnostics>
Error (line 10): type mismatch
</file_diagnostics>
```

## Parsing (`UpdateFileData` dataclass)

```python
# src/tunacode/ui/renderers/tools/update_file.py:27-39
@dataclass
class UpdateFileData:
    filepath: str
    filename: str        # Path(filepath).name
    root_path: Path      # Path.cwd()
    message: str         # "File '...' updated successfully."
    diff_content: str    # Full unified diff text
    additions: int       # Lines starting with + (not +++)
    deletions: int       # Lines starting with - (not ---)
    hunks: int           # Lines starting with @@
    diagnostics_block: str | None
```

Parsing splits on `"\n--- a/"` delimiter to separate message from diff.

## 4-Zone Rendering Layout

| Zone | Content | Rich Component |
|------|---------|----------------|
| Header | `filename.py  +3 -1` | `Text` (bold name, green adds, red dels) |
| Params | `> relative/path/to/file.py` | `Text` (dim arrow, dim underline path) |
| Viewport | Syntax-highlighted diff | `Syntax(diff, "diff", theme="monokai", word_wrap=True)` |
| Status | `1 hunk  [20/45 lines]  150ms` | `Text` (dim) |
| Diagnostics (optional) | Color-coded error/warning list | Custom renderables |

Zones separated by `Text("\n")` objects. Wrapped in `Group(*content_parts)`.

## Panel Metadata

```python
PanelMeta(
    css_class="tool-panel",
    border_title="[green]update_file[/] [done]",
    border_subtitle="[dim]HH:MM:SS[/]",
)
```

Applied by `ChatContainer.write()` as CSS classes and Textual border decorations.

## Viewport Constraints

- `TOOL_VIEWPORT_LINES` -- Max lines shown (truncates with indicator)
- `MIN_VIEWPORT_LINES` -- Min lines (pads with empty lines)
- Defined in `src/tunacode/core/ui_api/constants.py` (re-exported from `src/tunacode/constants.py`)

## Syntax Highlighting

Currently: `Syntax(truncated_diff, "diff", theme="monokai", word_wrap=True)`

- Pygments `"diff"` lexer handles `+/-/@@` line coloring
- Monokai theme hardcoded at `update_file.py:142`
- No TCSS styling for diff -- all handled by Rich Syntax

## Other Diff Rendering Location

- `src/tunacode/ui/renderers/panels.py:203` -- Also uses `Syntax(diff, "diff", theme="monokai", word_wrap=True)` (generic fallback path)

## Registry vs Routing

- `@tool_renderer` decorator registers into `_renderer_registry` (base.py:137)
- `tool_panel_smart()` uses hardcoded `renderer_map` dict (panels.py:504-512)
- Registry exposed via `get_renderer()` and `list_renderers()` but NOT used by dispatch

## Error Paths

| Condition | Location | Behavior |
|-----------|----------|----------|
| File not found | update_file.py:27-30 | `ToolRetryError` |
| Text not found | update_file.py:37-43 | `ToolRetryError` with 20-line preview |
| No-op replacement | update_file.py:46-49 | `ToolRetryError` |
| Parse failure | update_file.py renderer L61,70 | Returns `None`, falls back to generic `tool_panel()` |

## Dependencies

- `update_file.py` -> `difflib` (stdlib)
- `update_file.py` -> `tools/utils/text_match.py` (fuzzy replace)
- `update_file.py` -> `tools/lsp_utils.py` (diagnostics injection)
- `update_file renderer` -> `renderers/tools/base.py` (BaseToolRenderer)
- `update_file renderer` -> `renderers/tools/diagnostics.py` (diagnostic parsing/rendering)
- `update_file renderer` -> `renderers/tools/syntax_utils.py` (shared syntax utilities)
- `panels.py` -> all tool renderers (hardcoded imports)
- `chat.py` -> `CopyOnSelectStatic` / `SelectableRichVisual` (Rich->Textual bridge)

## All Tool Renderers (for pattern reference)

```
src/tunacode/ui/renderers/tools/
  __init__.py        -- Re-exports get_renderer, list_renderers, tool_renderer
  base.py            -- BaseToolRenderer[T], registry, PanelMeta
  update_file.py     -- UpdateFileRenderer
  bash.py            -- Bash tool renderer
  grep.py            -- Grep tool renderer
  glob.py            -- Glob tool renderer
  list_dir.py        -- List directory renderer
  read_file.py       -- Read file renderer
  write_file.py      -- Write file renderer
  web_fetch.py       -- Web fetch renderer
  diagnostics.py     -- Diagnostics parsing/rendering (shared)
  syntax_utils.py    -- Shared syntax utilities
```
