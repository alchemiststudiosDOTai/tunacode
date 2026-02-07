# Research -- Text Selection Broken on Agent Response Panels

**Date:** 2026-02-07
**Owner:** agent
**Phase:** Research
**git_commit:** b025379999e67ebc1eb0be3cc387bdfe9e0212a8
**tags:** text-selection, copy-to-clipboard, RichVisual, offset-metadata, CopyOnSelectStatic
**last_updated:** 2026-02-07
**last_updated_note:** Root cause identified -- RichVisual missing offset metadata

## Goal

Determine why text selection (highlight-to-copy) doesn't work on agent response panels. Users must hold Shift to select, get no visual feedback, while other widgets in the TUI support free selection with auto-copy.

## Root Cause (Confirmed)

**`RichVisual.render_strips()` does not inject `offset` metadata into rendered segments.** Textual's text selection system requires `offset` metadata in each segment's style to map screen coordinates to text positions. Without it, selection never starts.

### The Selection Chain (How It Breaks)

```
1. User clicks on agent panel text
2. screen.py:1581  -- get_widget_and_offset_at(x, y) called
3. _compositor.py:927-947  -- Iterates rendered segments looking for style._meta["offset"]
4. _compositor.py:949  -- No offset found -> returns (widget, None)
5. screen.py:1591  -- select_offset is None -> _select_start is NEVER SET
6. screen.py:1547  -- On drag, _selecting=True but no _select_start -> no selection range
7. Result: No visual highlight, no copy, selection doesn't happen
```

### Why Other Widgets Work

When `CopyOnSelectStatic(Text("plain text"))` is created:
```
visualize() at visual.py:89-90
  -> isinstance(obj, Text) is True
  -> Content.from_rich_text(obj, console)  [converts to Content]
```
`Content.render_strips()` at `content.py:1478` calls `rich_style_with_offset(x, y)` on every segment, embedding `{"offset": (x, y)}` in the style meta. Selection works.

When `CopyOnSelectStatic(Group(Markdown(...)))` is created (agent responses):
```
visualize() at visual.py:88,92-93
  -> is_renderable(obj) is True, not isinstance(obj, Text)
  -> RichVisual(widget, rich_cast(obj))  [wraps in RichVisual]
```
`RichVisual.render_strips()` at `visual.py:291-321` renders through Rich's console but **never adds offset metadata**. The `selection` and `selection_style` parameters are accepted but ignored.

### Evidence

| Widget content | Visual type | Has offset meta | Selection works |
|---|---|---|---|
| `Text("user message")` | `Content` | YES (`content.py:1478`) | YES |
| `Markdown("agent response")` | `RichVisual` | NO | NO |
| `Group(Markdown(...), Text(...))` | `RichVisual` | NO | NO |
| `Panel(Group(Markdown(...)))` (pre-migration) | `RichVisual` | NO | NO |

Note: This issue existed BEFORE the panel-to-CSS migration. `Panel(Group(...))` also goes through `RichVisual` because `Panel` is a Rich renderable, not a `Text`. The migration didn't cause this; it just became more noticeable.

## Relevant Files

| File | Why It Matters |
|------|---------------|
| [`src/tunacode/ui/widgets/chat.py:137`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b0253799/src/tunacode/ui/widgets/chat.py#L137) | `CopyOnSelectStatic(renderable)` created here -- where the Visual type gets determined |
| [`src/tunacode/ui/widgets/chat.py:43-78`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b0253799/src/tunacode/ui/widgets/chat.py#L43) | `CopyOnSelectStatic` -- has `selection_updated()` and `_copy_current_selection()` but they never fire for Rich renderables |
| [`.venv/.../textual/visual.py:88-93`] | `visualize()` -- `Text` goes to `Content`, everything else goes to `RichVisual` |
| [`.venv/.../textual/visual.py:291-321`] | `RichVisual.render_strips()` -- renders Rich content but adds NO offset metadata and ignores selection params |
| [`.venv/.../textual/content.py:1478`] | `Content.render_strips()` -- DOES add offset metadata via `rich_style_with_offset(x, y)` |
| [`.venv/.../textual/_compositor.py:927-949`] | `get_widget_and_offset_at()` -- scans segment meta for `"offset"` key; returns `None` if missing |
| [`.venv/.../textual/screen.py:1578-1599`] | MouseDown handler -- skips `_select_start` when offset is `None` |
| [`src/tunacode/ui/renderers/agent_response.py:137`](https://github.com/alchemiststudiosDOTai/tunacode/blob/b0253799/src/tunacode/ui/renderers/agent_response.py#L137) | `Markdown(content)` wrapped in `Group()` -- the Rich renderable that triggers `RichVisual` path |

## Proposed Fix

### Approach: Create `SelectableRichVisual` that injects offset metadata

Override `RichVisual.render_strips()` to post-process strips with offset metadata, enabling Textual's selection system to work with Rich renderables.

**Where**: `src/tunacode/ui/widgets/chat.py`

**What**:
1. Create a `SelectableRichVisual(RichVisual)` subclass
2. Override `render_strips()` to:
   - Call parent to get the raw strips
   - Iterate strips adding `offset` metadata (`{"offset": (x, y)}`) to each segment's style via `Style._meta`
   - Apply selection highlighting when `selection` is not None
3. Override `visual` property in `CopyOnSelectStatic` to use `SelectableRichVisual` instead of letting `visualize()` return plain `RichVisual`

**Key detail**: The offset metadata format is `{"offset": (x, y)}` where `x` = character position within the line and `y` = line number. This must be injected via `rich.style.Style(meta={"offset": (x, y)})` or by calling `Style.__add__(Style(meta={"offset": (x, y)}))` on each segment's existing style.

### Alternative: Pre-render to Text

Pre-render the `Group(Markdown(...))` using `console.render_lines()` to get styled text, then flatten to a multi-line `Text` object. Pass that `Text` to `CopyOnSelectStatic` so `visualize()` routes it through `Content.from_rich_text()`.

**Trade-off**: Simpler but may lose some Rich rendering fidelity (e.g., inline objects, custom padding in code blocks).

## Syntax Highlighting (Not Broken)

Initial investigation confirmed that Rich syntax highlighting in code blocks IS correctly preserved through the `_Styled` wrapper. The CSS `color` property acts as a fallback, not an override. Monokai colors survive because `Style._add()` at `rich/style.py:737` gives precedence to the segment's color when present.

This was a red herring -- the actual issue is text selection, not syntax highlighting.

## Key Patterns / Solutions Found

- **`RichVisual` is selection-blind**: It accepts `selection` and `selection_style` params in `render_strips()` but ignores them completely.
- **Offset metadata is the selection key**: Without `meta={"offset": (x, y)}` on segment styles, `_compositor.get_widget_and_offset_at()` returns `(widget, None)`, preventing selection start.
- **`Content` vs `RichVisual` split**: `visualize()` at `visual.py:88-93` routes `Text` to `Content` (selectable) and everything else to `RichVisual` (not selectable). This is the fundamental branch point.
- **`Style._add` preserves inline colors**: CSS base style acts as fallback; Rich inline styles take precedence. Not the issue but important for the fix (offset meta must be added without breaking existing styles).

## Knowledge Gaps

1. How Textual's selection highlighting visual is rendered (the `screen--selection` component style) -- need to apply this in the custom `render_strips`
2. Whether `Selection.extract()` works correctly with reconstructed offset metadata from `RichVisual` output
3. Whether `rich_style_with_offset` from `textual.style.Style` can be reused or if we need to build the meta manually on `rich.style.Style` objects

## References

- Textual `RichVisual.render_strips`: `.venv/lib/python3.13/site-packages/textual/visual.py:291-321`
- Textual `Content.render_strips`: `.venv/lib/python3.13/site-packages/textual/content.py:1460-1510`
- Textual `_compositor.get_widget_and_offset_at`: `.venv/lib/python3.13/site-packages/textual/_compositor.py:889-949`
- Textual `Screen._forward_event` (selection handler): `.venv/lib/python3.13/site-packages/textual/screen.py:1578-1599`
- Textual `visualize()`: `.venv/lib/python3.13/site-packages/textual/visual.py:65-102`
- Rich `Style._add`: `.venv/lib/python3.13/site-packages/rich/style.py:729-751`
- Commit `2cd1d750`: Panel-to-CSS migration
- Commit `0fd3c798`: Auto-copy highlighted text feature
