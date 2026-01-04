# Research – TunaCode TUI Visual Design System & UI Features

**Date:** 2026-01-04
**Owner:** agent
**Phase:** Research
**Inspiration:** OpenCode TUI (SolidJS-based)

## Goal

Map out all the visual design elements, color coding, feedback mechanisms, and UI features in TunaCode's TUI. Document how AI vs user messages are differentiated, how theming works, and identify gaps compared to modern polished TUIs like OpenCode.

---

## Findings

### Core Architecture

TunaCode's TUI is built with:
- **Textual** - Python TUI framework (CSS-like styling)
- **Rich** - Text formatting and Markdown rendering
- **TCSS stylesheets** - 5 stylesheet files for theming and layout
- **NeXTSTEP design philosophy** - 1990s inspired 3D bevels and uniformity

### Relevant Files & Why They Matter

| File | Purpose |
|------|---------|
| `src/tunacode/ui/app.py` | Main TUI application, message flow, streaming |
| `src/tunacode/constants.py` | Color palettes (`UI_COLORS`, `NEXTSTEP_COLORS`), theme builders |
| `src/tunacode/ui/styles.py` | Rich style constants (`STYLE_PRIMARY`, `STYLE_ERROR`, etc.) |
| `src/tunacode/ui/styles/theme-nextstep.tcss` | NeXTSTEP 3D bevel overrides (304 lines) |
| `src/tunacode/ui/styles/layout.tcss` | Main layout, viewport states, editor |
| `src/tunacode/ui/styles/panels.tcss` | Tool panel status-based colors |
| `src/tunacode/ui/widgets/editor.py` | Input prompt with bash mode, paste buffer |
| `src/tunacode/ui/widgets/status_bar.py` | 3-zone bottom status bar |
| `src/tunacode/ui/widgets/resource_bar.py` | Top bar with token usage, cost, LSP |
| `src/tunacode/ui/renderers/panels.py` | 4-zone tool panel system, smart router |
| `src/tunacode/ui/screens/theme_picker.py` | Interactive theme picker with live preview |

---

## Key Patterns / Solutions Found

### 1. Theming System

**Architecture:** Textual themes + CSS class-based overrides

**Color Palettes (constants.py:83-112):**

```python
UI_COLORS = {
    "background": "#1a1a1a",      # Dark charcoal
    "surface": "#252525",          # Lighter surface
    "border": "#ff6b9d",           # Pink accent
    "text": "#e0e0e0",             # Light gray
    "muted": "#808080",            # Gray
    "primary": "#00d7d7",          # Cyan
    "accent": "#ff6b9d",           # Pink
    "success": "#4ec9b0",          # Teal
    "warning": "#c3e88d",          # Lime green
    "error": "#f44747",            # Red
}

NEXTSTEP_COLORS = {
    "background": "#acacac",       # Desktop gray
    "surface": "#c8c8c8",          # Medium gray
    "bevel_light": "#e8e8e8",      # 3D highlight
    "bevel_dark": "#606060",       # 3D shadow
    # ... monochrome semantic colors
}
```

**Available Themes (13 total):**
- **Custom (2):** `tunacode` (dark), `nextstep` (light)
- **Textual Built-in (11):** `dracula` (default), `nord`, `gruvbox`, `catppuccin-mocha`, `tokyo-night`, `monokai`, `flexoki`, `catppuccin-latte`, `solarized-light`, `textual-dark`, `textual-light`

**Theme Switching Flow:**
1. `/theme [name]` command or picker modal
2. `app.theme = theme_name` triggers `watch_theme()`
3. CSS class `.theme-{name}` added to app root
4. Theme-specific TCSS rules activate
5. Config persisted to `~/.tunacode/tunacode.json`

---

### 2. Message Differentiation (User vs AI)

**User Messages:**
| Property | Implementation |
|----------|---------------|
| Gutter | `"│ "` prefix on every line |
| Color | Cyan (`#00d7d7` / `STYLE_PRIMARY`) |
| Format | Plain text with word wrapping |
| Timestamp | `"│ you I:MM PM"` at bottom |
| Paste handling | Shows `"[[ N lines ]]"` placeholder |

**AI Messages:**
| Property | Implementation |
|----------|---------------|
| Label | `"agent:"` in pink accent |
| Content | Rich Markdown rendering |
| Streaming | Separate `#streaming-output` widget |
| Throttle | 100ms update interval |

**Code References:**
- User formatting: `src/tunacode/ui/repl_support.py:34-91`
- AI rendering: `src/tunacode/ui/app.py:301-302`

---

### 3. Status Indicators

**Resource Bar (Top):**
- Model name in primary color
- Token usage: Circle visualization (`●◕◑◔○`) with color coding
  - Green: >60% remaining
  - Yellow: 30-60%
  - Red: <30%
- Session cost: `"$0.42"` in green
- LSP status: `"LSP: ruff"` when active

**Status Bar (Bottom) - 3 Zones:**
1. **Left:** Git branch + directory (`"main ● project"`)
2. **Center:** Edited files (`"edited: file1.py, file2.py"`)
3. **Right:** Operation status (`"running: grep"`)

**Viewport Border States:**
- Normal: Pink border (`$border`)
- Streaming: Pink accent (`$accent`)
- Paused: Yellow-green (`$warning`)
- NeXTSTEP: 3D bevels (raised normal, pressed streaming)

---

### 4. Tool Panel System

**4-Zone Architecture (NeXTSTEP-inspired):**

| Zone | Content |
|------|---------|
| **Header** | Tool name + status (`$ command → ok`) |
| **Parameters** | Context (cwd, timeout, file path) |
| **Viewport** | Primary content (stdout, file, results) |
| **Status** | Metrics (lines, duration, truncation) |

**Status-Based Colors:**
- Running: Cyan/accent border
- Completed: Green border
- Failed: Red border

**Code Reference:** `src/tunacode/ui/renderers/panels.py:484-532`

---

### 5. Input Editor Features

| Feature | Description |
|---------|-------------|
| **Multi-line** | Wraps within 6-line fixed height |
| **Bash Mode** | `!` prefix, green border, status indicator |
| **Paste Buffer** | Stores large pastes, shows `[[ N lines ]]` |
| **File Autocomplete** | `@` trigger, dropdown completions |
| **Command Autocomplete** | `/` trigger for slash commands |

**Code Reference:** `src/tunacode/ui/widgets/editor.py`

---

### 6. Modal/Screen System

**Available Screens:**
- `ThemePickerScreen` - Live preview, arrow navigation
- `ModelPickerScreen` - Two-step: provider → model
- `SessionPickerScreen` - Session selection
- `UpdateConfirmScreen` - Version update prompt
- `SetupScreen` - Initial configuration

**Features:**
- Textual's `Screen[T]` with typed return values
- Escape to cancel, Enter to confirm
- Real-time filtering with Input widget
- Live preview (theme changes immediately on highlight)

---

### 7. Notification System

**Current Implementation:** Textual's built-in `app.notify()`

**Usage Patterns (42 calls found):**
- `"information"` (default): Config saved, mode changes
- `"warning"`: Invalid usage, timeouts
- `"error"`: Unknown commands, failed operations

**Limitations:**
- Default styling only
- No custom positioning
- No rich content (icons, actions)
- No duration control

---

## Gap Analysis: TunaCode vs OpenCode

### What OpenCode Has That TunaCode Lacks

| Feature | OpenCode | TunaCode |
|---------|----------|----------|
| **Spinner** | Knight Rider animation with trail, bloom, hold frames | Basic Textual LoadingIndicator toggle |
| **Toast System** | Custom component with positioning, auto-dismiss, variants | Default Textual notify() |
| **Dialog System** | Custom stack management, click-outside-close, backdrop | Textual Screen modals |
| **Autocomplete** | Fuzzy search (fuzzysort), mouse hover, score boosting | Basic Input filtering |
| **Tips System** | 103 "Did You Know" tips with highlight syntax | None |
| **Header Effects** | Gradient fade using `▄`/`▀` characters | Solid bar |
| **Agent Colors** | Per-agent colored borders/indicators | Single accent color |
| **Attachments** | Image thumbnails, PDF badges | Paste buffer only |
| **Reasoning Display** | Dimmed "Thinking:" with left border | Not implemented |

### Detailed Feature Gaps

**1. Animation System**
- OpenCode: 6-step alpha gradient trail, 40ms frame rate, bidirectional sweep
- TunaCode: CSS display toggle only

**2. Semantic Colors**
- OpenCode: 45+ semantic color properties (markdown, diff, syntax)
- TunaCode: ~10 core colors in palette

**3. Visual Hierarchy**
- OpenCode: Agent-specific colors, reasoning dimming, tool grouping
- TunaCode: Single accent color, flat hierarchy

**4. Feedback Mechanisms**
- OpenCode: Retry counters, interrupt feedback, double-escape visual
- TunaCode: Basic status bar updates

**5. Responsive Design**
- OpenCode: Tall/wide modes, dynamic sizing, adaptive padding
- TunaCode: Fixed layouts

---

## Recommendations for Improvement

### High Priority

1. **Knight Rider Spinner**
   - Port animation logic to Textual worker thread
   - Use Rich Text with color interpolation
   - Add agent-colored variants

2. **Custom Toast Component**
   - Absolute positioning (top-right)
   - Auto-dismiss with configurable timeout
   - Variant-based border colors
   - Optional title + message

3. **Thinking/Reasoning Display**
   - Dimmed text style
   - Left border indicator
   - "Thinking:" prefix
   - Collapse/expand for long reasoning

4. **Enhanced Autocomplete**
   - Integrate fuzzysort or similar
   - Score boosting for prefix matches
   - Mouse hover selection
   - Recent/favorites section

### Medium Priority

5. **Gradient Headers**
   - Use `▄`/`▀` characters for fade effect
   - Apply to viewport/panel edges

6. **Did You Know Tips**
   - Collection of keyboard shortcuts and features
   - Random selection on startup
   - Highlight syntax for keybinds

7. **Agent-Specific Colors**
   - Per-agent color assignment
   - Colored left borders on user messages
   - Spinner color matches active agent

8. **Progress Indicators**
   - For file indexing
   - For long-running bash commands
   - For multi-step operations

### Low Priority

9. **Attachment Previews**
   - Image dimension badges
   - PDF page count indicators
   - Clickable file paths

10. **Enhanced Diff Colors**
    - 12 properties like OpenCode
    - Line number coloring
    - Add/remove background colors

---

## Knowledge Gaps

- Performance impact of animation on large outputs
- Accessibility considerations for color-blind users
- Terminal compatibility for gradient effects
- Integration with Textual's reactive system for animations

---

## References

### TunaCode Files
- Theme system: `src/tunacode/constants.py`, `src/tunacode/ui/app.py:156-161`
- Styling: `src/tunacode/ui/styles/` (5 TCSS files)
- Widgets: `src/tunacode/ui/widgets/` (7 widget files)
- Renderers: `src/tunacode/ui/renderers/` (14 renderer files)
- Screens: `src/tunacode/ui/screens/` (6 screen files)

### OpenCode Inspiration
- Spinner: `packages/opencode/src/cli/cmd/tui/ui/spinner.ts`
- Toast: `packages/opencode/src/cli/cmd/tui/ui/toast.tsx`
- Theme: `packages/opencode/src/cli/cmd/tui/context/theme.tsx`
- Did You Know: `packages/opencode/src/cli/cmd/tui/component/did-you-know.tsx`

### Design Reference
- `.claude/skills/neXTSTEP-ui/SKILL.md` - NeXTSTEP design guidelines
- `.claude/skills/neXTSTEP-ui/NeXTSTEP_User_Interface_Guidelines_Release_3_Nov93.pdf`
