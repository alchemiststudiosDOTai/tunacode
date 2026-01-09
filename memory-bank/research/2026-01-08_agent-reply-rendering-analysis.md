# Research – Agent Reply Rendering Analysis

**Date:** 2026-01-08
**Owner:** Claude
**Phase:** Research

## Goal

Map out how agent replies are currently rendered, identify why they feel "random" and unstructured, and document NeXTSTEP-informed design improvements.

## The Problem

Agent text responses are rendered as **raw Markdown dumped into RichLog** with just an "agent:" label. No structure, no zones, no visual containment. Tool results get beautiful 4-zone panels; agent text gets nothing.

**Current code** (`src/tunacode/ui/app.py:307-310`):
```python
if self.current_stream_text and not self._streaming_cancelled:
    self.rich_log.write("")
    self.rich_log.write(Text("agent:", style="accent"))
    self.rich_log.write(Markdown(self.current_stream_text))
```

This violates NeXTSTEP's core principle: **"Objects that look the same should act the same."** Tool outputs have panels; agent text floats freely. Inconsistent.

## Findings

### Current Architecture

| Component | Location | Purpose |
|-----------|----------|---------|
| `RichLog` widget | `app.py:118` | Persistent message history |
| `streaming_output` Static | `app.py:119` | Live streaming display |
| Tool renderers | `renderers/tools/*.py` | 9 structured panel renderers |
| `BaseToolRenderer` | `renderers/tools/base.py:245` | 4-zone layout pattern |

### What Tool Results Get (That Agent Text Doesn't)

1. **Panel containment** - Border with status-based coloring
2. **4-zone layout** - Header, Params, Viewport, Status
3. **Metrics** - Duration, line counts, truncation info
4. **Syntax highlighting** - Consistent monokai theme
5. **Visual hierarchy** - Separators between zones
6. **Timestamp** - Top-right corner

### Agent Text Gets

1. `"agent:"` label in accent color
2. Raw Markdown dump
3. Nothing else

### Information Density Gap

From NeXTSTEP reference (DoomEd screenshot):
- Multiple inspector panels with **clear purposes**
- Dense but **organized information zones**
- Every zone has a **visible boundary**
- Tool palettes and browsers have **consistent framing**

Current agent output has **zero framing** - it's just text soup in the viewport.

## NeXTSTEP Principles That Apply

### 1. Information Hierarchy & Zoning

> "Divide interface into zones with distinct purposes. Users learn where to look."

Agent responses should have:
```
┌─ agent ─────────────────────────── 12:34 PM ─┐
│                                               │
│  [Response content with proper structure]     │  ← VIEWPORT
│                                               │
├───────────────────────────────────────────────┤
│  tokens: 1.2k  │  thinking: 2.3s  │  model   │  ← STATUS
└───────────────────────────────────────────────┘
```

### 2. Consistency

> "Objects that look the same should act the same."

If tool outputs get panels, agent responses should get panels. Same visual language.

### 3. Feedback Principles

> "User must always see result of their action."

Currently missing:
- How long did the agent think?
- How many tokens were used?
- What model responded?

This metadata exists but isn't displayed.

## Proposed 3-Zone Agent Response Layout

Based on NeXTSTEP and existing `BaseToolRenderer` pattern:

```
┌─ agent ────────────────────────────── HH:MM ─┐  ← HEADER
│                                               │
│  Markdown-rendered response content           │
│  with proper code highlighting                │  ← VIEWPORT
│  and structure                                │
│                                               │
├───────────────────────────────────────────────┤
│  1.2k tokens  ·  2.3s  ·  claude-3.5-sonnet  │  ← STATUS
└───────────────────────────────────────────────┘
```

**Simpler than tool panels** (3 zones not 4) because:
- No "params" zone needed - agent responses don't have input parameters
- Header is minimal - just "agent" + timestamp
- Status shows metrics user cares about

## Key Files to Modify

| File | Change |
|------|--------|
| `src/tunacode/ui/app.py:307-310` | Replace raw write with renderer call |
| `src/tunacode/ui/renderers/` | Add `agent_response.py` renderer |
| `src/tunacode/ui/renderers/panels.py` | Add `render_agent_response()` helper |

## Design Decisions Needed

1. **Border color for agent responses?**
   - Option A: `accent` (pink) - matches "agent:" label
   - Option B: `primary` (cyan) - distinguishes from tools
   - Option C: No border, just separator lines (lighter weight)

2. **Status bar metrics?**
   - Token count (available from state_manager)
   - Response time (can track from request start)
   - Model name (available from config)
   - All three?

3. **Streaming display?**
   - Current: Raw markdown in separate `Static` widget
   - Keep as-is (simpler) or panel during stream too?

## Related Files

**Rendering infrastructure:**
- `src/tunacode/ui/renderers/tools/base.py` - BaseToolRenderer pattern
- `src/tunacode/ui/renderers/panels.py` - Panel helpers
- `src/tunacode/ui/renderers/tools/syntax_utils.py` - Highlighting

**Agent response flow:**
- `src/tunacode/ui/app.py:387-403` - Streaming callback
- `src/tunacode/ui/app.py:298-317` - Finalization
- `src/tunacode/core/agents/agent_components/streaming.py` - Token streaming

**Styling:**
- `src/tunacode/ui/styles/theme-nextstep.tcss` - Theme colors
- `src/tunacode/constants.py:99-110` - UI_COLORS palette

## Knowledge Gaps

1. Where is response timing tracked? Need to expose duration.
2. Where is token count stored after response? Need to pull from state_manager.
3. Should user messages also get panel treatment for consistency?

## Visual Reference

NeXTSTEP DoomEd screenshot (`.claude/skills/neXTSTEP-ui/doomed_nextstep_reference.png`) shows:
- Every panel has clear header with title
- Dense content within bounded zones
- Consistent gray beveled chrome
- Multiple inspectors can coexist visually

Apply same discipline to agent responses.

## Next Steps

1. Create `AgentResponseRenderer` following `BaseToolRenderer` pattern
2. Wire up metrics (tokens, duration, model) to renderer
3. Update `app.py` finalization to use new renderer
4. Consider user message panel treatment for full consistency
