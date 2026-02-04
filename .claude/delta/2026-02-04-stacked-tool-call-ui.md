---
date: 2026-02-04
type: feature
scope: ui
impact: medium
---

# Stacked Tool Call UI (Debounced Tool Burst Rendering)

## Summary

Added a compact, NeXTSTEP-aligned "stacked" tool batch display to reduce vertical spam when many tool results arrive in a short burst.

When more than 3 tool results are emitted back-to-back, the UI now renders a single panel containing one concise row per tool (instead of multiple full tool panels).

## Changes

### UI batching in `src/tunacode/ui/app.py`

- Added a `ToolResultDisplay` buffer and a debounce timer (`App.set_timer`, `Timer.stop()`).
- `on_tool_result_display()` now buffers results and schedules `_flush_tool_results()`.
- `_flush_tool_results()` chooses:
  - `render_stacked_tools()` when `len(batch) > 3`
  - existing per-tool panel rendering when `len(batch) <= 3`

### New renderer: `src/tunacode/ui/renderers/tools/stacked.py`

- Introduced `render_stacked_tools(tools, max_line_width)`.
- Preserves explicit width verification via `tool_panel_frame_width(max_line_width)`.
- Shows a primary argument per tool (e.g., `glob.pattern`, `read_file.filepath`, `bash.command`) with truncation.
- Marks non-completed tools as failures with error styling and a `[FAILED]` suffix.

### Exports

- Exported `render_stacked_tools` from `src/tunacode/ui/renderers/tools/__init__.py`.

## Documentation updates

- Updated `docs/codebase-map/modules/ui-overview.md` to document:
  - Debounced tool batching
  - The new stacked renderer
  - Updated AI response flow

## Verification

- `uv run ruff check --fix .`
- `uv run pytest`
- Rich console smoke rendering confirmed stacked panel output shape and failure styling.
