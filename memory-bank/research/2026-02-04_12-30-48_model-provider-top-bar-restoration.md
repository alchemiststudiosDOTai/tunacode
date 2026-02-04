# Research – Model/Provider Top Bar Restoration

**Date:** 2026-02-04
**Owner:** user
**Phase:** Research
**last_updated:** 2026-02-04
**last_updated_by:** claude
**git_commit:** 3a195b1b
**tags:** [ui, resource-bar, model-display, ux]

## Goal

Map out how the model/provider display was moved from the UI top bar to the agent response panel, and document how to restore it to the leftmost position in the top bar.

---

## Findings

### Relevant Files & Why They Matter

| File | Location | Purpose |
|------|----------|---------|
| `resource_bar.py` | `src/tunacode/ui/widgets/resource_bar.py` | Top bar widget - displays tokens, cost, LSP status. Model was removed from here in PR #218 |
| `agent_response.py` | `src/tunacode/ui/renderers/agent_response.py` | Agent response panels - currently shows model in status bar (lines 124-125, 191-192) |
| `app.py` | `src/tunacode/ui/app.py` | Main app - updates ResourceBar via `_update_resource_bar()` (line 370-381) |
| `styles.py` | `src/tunacode/ui/styles.py` | Style constants including `STYLE_PRIMARY` that was removed in PR #218 |

### Historical Implementation

**Original Design (commit ab1a0361 - Dec 2025):**
```python
# src/tunacode/ui/widgets/resource_bar.py _refresh_display()
content = Text.assemble(
    (self._model, "cyan"),           # <-- Model displayed FIRST (leftmost)
    (sep, "dim"),
    (circle_char, circle_color),     # Token circle
    (f" {remaining_pct:.0f}%", circle_color),  # Token percentage
    (sep, "dim"),
    (session_cost_str, "green"),     # Session cost
)
```

**When Removed (commit ea2ae9fb - PR #218, Jan 8 2026):**
```diff
 parts: list[tuple[str, str]] = [
-    (self._model, STYLE_PRIMARY),
-    (sep, STYLE_MUTED),
     (circle_char, circle_color),
     (f" {remaining_pct:.0f}%", circle_color),
```

**Commit message quote:** "fix: remove model name from top bar (shown in agent panel now)"

### Current State

**Top bar (ResourceBar) displays left-to-right:**
1. Token circle (resource_bar.py:99)
2. Token percentage (resource_bar.py:100)
3. Separator " - " (resource_bar.py:101)
4. Session cost (resource_bar.py:102)
5. *(conditional)* LSP server name (resource_bar.py:109)
6. *(conditional)* LSP indicator (resource_bar.py:110)

**Model is ONLY shown in:**
- Agent response panel status bars (agent_response.py:124-125, 191-192)
- Model picker modal
- Session picker

### How to Restore Model to Top Bar

**File to modify:** `src/tunacode/ui/widgets/resource_bar.py`

**Location:** `_refresh_display()` method around line 98

**Change:** Insert model as the first element in the `parts` list:

```python
def _refresh_display(self) -> None:
    sep = RESOURCE_BAR_SEPARATOR
    session_cost_str = RESOURCE_BAR_COST_FORMAT.format(cost=self._session_cost)

    remaining_pct = self._calculate_remaining_pct()
    circle_char = self._get_circle_char(remaining_pct)
    circle_color = self._get_circle_color(remaining_pct)

    # Restore STYLE_PRIMARY import if needed (removed in PR #218)
    from tunacode.ui.styles import STYLE_PRIMARY

    parts: list[tuple[str, str]] = [
        (self._model, STYLE_PRIMARY),   # <-- ADD THIS LINE (leftmost)
        (sep, STYLE_MUTED),              # <-- ADD THIS LINE (separator)
        (circle_char, circle_color),
        (f" {remaining_pct:.0f}%", circle_color),
        (sep, STYLE_MUTED),
        (session_cost_str, STYLE_SUCCESS),
        # ... LSP conditional parts
    ]
```

**Required import restoration (if missing):**
- `STYLE_PRIMARY` was removed from resource_bar.py imports in PR #218
- Add to line 12: `from tunacode.ui.styles import STYLE_PRIMARY`

---

## Key Patterns / Solutions Found

1. **ResourceBar uses Text.assemble() with tuple list for left-to-right ordering** - Inserting at index 0 or prepending to list ensures leftmost position
2. **Model data already flows to ResourceBar** - `update_stats(model=...)` is called from app.py:370, just needs to be rendered
3. **Agent panels use `_format_model()` to abbreviate provider prefixes** (ANTH/, OA/, GOOG/) - ResourceBar currently shows full model name

---

## Knowledge Gaps

- Should the model in the top bar use the same `_format_model()` abbreviation as agent panels, or show full name?
- Is the "cyan" color from original implementation preferred, or restore `STYLE_PRIMARY`?

---

## References

- **Original implementation:** https://github.com/alchemiststudiosDOTai/tunacode/blob/ab1a0361389a771b2c8ed6c6e9cf8965b9581c88/src/tunacode/ui/widgets/resource_bar.py#L81-L93
- **When removed (PR #218):** https://github.com/alchemiststudiosDOTai/tunacode/blob/ea2ae9fb910f570cf3e680f7b62e6fc415d21ef4/src/tunacode/ui/widgets/resource_bar.py#L164-L167
- **Current ResourceBar:** src/tunacode/ui/widgets/resource_bar.py:90-113
- **Current app update:** src/tunacode/ui/app.py:370-381
- **Agent response model display:** src/tunacode/ui/renderers/agent_response.py:56-78 (_format_model function)
