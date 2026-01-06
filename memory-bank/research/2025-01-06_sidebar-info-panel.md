# Research - Right-Side Info Panel (Sidebar)

**Date:** 2025-01-06
**Owner:** claude
**Phase:** Research

## Goal

Research how to implement a right-side "info at a glance" panel for the TunaCode TUI, inspired by OpenCode/Crush's sidebar design, following NeXTSTEP design principles.

## Findings

### Current TunaCode Layout Structure

The app uses vertical stacking (top to bottom):

```
┌─────────────────────────────────────────────────┐
│ ResourceBar (1 line)                            │  model, tokens, cost, LSP
├─────────────────────────────────────────────────┤
│                                                 │
│ #viewport (1fr - flexible)                      │  RichLog, streaming output
│                                                 │
├─────────────────────────────────────────────────┤
│ Editor (6 lines)                                │  user input
├─────────────────────────────────────────────────┤
│ StatusBar (1 line)                              │  branch, edited files, action
└─────────────────────────────────────────────────┘
```

**Key Files:**
- `src/tunacode/ui/app.py:106-122` - compose() method defines layout
- `src/tunacode/ui/app.tcss` - CSS stylesheet (606 lines)
- `src/tunacode/ui/widgets/resource_bar.py` - Top bar (model/tokens/cost)
- `src/tunacode/ui/widgets/status_bar.py` - Bottom bar (branch/files/action)

### Current ResourceBar Content

Located at `src/tunacode/ui/widgets/resource_bar.py:56-183`:
1. Model name (e.g., "claude-sonnet-4-20250514")
2. Token usage circle indicator (visual: `●◕◑◔○`)
3. Remaining percentage (e.g., "85%")
4. Session cost (e.g., "$0.42")
5. LSP status (optional, if enabled)

### OpenCode/Crush Sidebar Design

Crush (formerly OpenCode) implements a right-side sidebar with **four sections**:

1. **Files Section** - Edited files with change metrics (+/-), file history
2. **LSP Section** - Active language servers, status
3. **MCP Section** - MCP server configurations
4. **Model Block** - Active model, token usage, cost, reasoning model

**Design Features:**
- Responsive layout adapting to terminal height
- Dynamic space allocation (`calculateAvailableHeight()`)
- Two modes: vertical (stacked) and compact/overlay (`ctrl+d` toggle)
- Priority: Files > LSP > MCP when space limited
- Min 2 items per section, max configurable (10 files, 8 LSP/MCP)

### NeXTSTEP Design Mapping

Following the NeXTSTEP zoning principles:

```
┌──────────────────────────────────┬────────────────┐
│      PERSISTENT STATUS           │   INFO PANEL   │
│      (ResourceBar - top)         │   (sidebar)    │
├──────────────────────────────────┤                │
│                                  │  - Model       │
│      PRIMARY VIEWPORT            │  - Tokens      │
│      (conversation/output)       │  - Cost        │
│                                  │  - Files       │
│                                  │  - LSP/MCP     │
├──────────────────────────────────┤                │
│      INPUT / COMMAND             │                │
│      (Editor at bottom)          │                │
├──────────────────────────────────┴────────────────┤
│              STATUS BAR (bottom)                  │
└───────────────────────────────────────────────────┘
```

**Rationale:** Right-side panel follows NeXTSTEP "Available Actions" zone placement, providing glanceable context without interrupting the main viewport flow.

## Proposed Sidebar Sections

Based on research, recommended sections for TunaCode:

| Section | Content | Priority |
|---------|---------|----------|
| **Model** | Model name, provider | High |
| **Usage** | Token usage (visual), remaining %, cost | High |
| **Files** | Recently edited files with +/- indicators | Medium |
| **Tools** | Last/current tool execution | Medium |
| **LSP** | Active language servers (if enabled) | Low |
| **Mode** | Plan mode indicator, session state | Low |

## Implementation Approach

### Option A: Dock-based (Recommended)

Use Textual's `dock: right` CSS property:

```python
# app.py compose()
def compose(self) -> ComposeResult:
    yield InfoPanel(id="info-panel")  # Docked widget
    yield self.resource_bar
    with Container(id="viewport"):
        yield self.rich_log
        # ...
    yield self.editor
    yield self.status_bar
```

```css
/* app.tcss */
#info-panel {
    dock: right;
    width: 28;
    height: 100%;
    border-left: solid $border;
    padding: 1;
}
```

**Pros:** Simple, widget removed from normal flow, automatic resizing
**Cons:** Less control over exact positioning

### Option B: Horizontal Container

Wrap viewport and sidebar in Horizontal:

```python
def compose(self) -> ComposeResult:
    yield self.resource_bar
    with Horizontal(id="main-layout"):
        with Container(id="viewport"):
            yield self.rich_log
        yield InfoPanel(id="info-panel")
    yield self.editor
    yield self.status_bar
```

**Pros:** More explicit control, easier to toggle visibility
**Cons:** More nesting, slightly more complex CSS

### Recommended Widget Structure

```python
class InfoPanel(Container):
    """Right-side info panel with glanceable status."""

    def compose(self) -> ComposeResult:
        yield Static("", id="panel-model")
        yield Static("", id="panel-usage")
        yield Static("", id="panel-files")
        yield Static("", id="panel-tools")
```

## Key Patterns / Solutions Found

- **Responsive sections:** Crush uses `getDynamicLimits()` to distribute space fairly
- **Visual indicators:** Token usage shown as circle fills (already in ResourceBar)
- **File tracking:** Session maintains edited files list (already in StatusBar)
- **Toggle support:** Compact mode via keybinding (`ctrl+d` in Crush)

## Knowledge Gaps

1. Should sidebar be collapsible/toggleable?
2. Exact width - 24, 28, or 32 characters?
3. Should we move ResourceBar content entirely to sidebar, or duplicate?
4. How to handle narrow terminals (< 100 columns)?

## References

- `src/tunacode/ui/app.py` - Main app layout
- `src/tunacode/ui/app.tcss` - CSS styling
- `src/tunacode/ui/widgets/resource_bar.py` - Current top bar implementation
- `src/tunacode/ui/widgets/status_bar.py` - Current bottom bar implementation
- [Crush/OpenCode GitHub](https://github.com/charmbracelet/crush) - Sidebar reference
- NeXTSTEP UI Guidelines - Design philosophy

---

*Research completed: 2025-01-06*
