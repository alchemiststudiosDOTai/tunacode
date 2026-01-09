# Agent Response Panel

**Date:** 2026-01-08
**Scope:** UI / Agent Output
**Status:** Canonical

## Overview

Agent text responses are rendered in styled panels matching the NeXTSTEP tool panel aesthetic. This provides visual consistency across all output types.

## Layout

```
┌─────────────────────────── agent ───────────────────────────┐
│                                                              │
│  [Markdown Content]                                          │
│  The agent's response with proper syntax highlighting,       │
│  code blocks, lists, and other markdown formatting.          │
│                                                              │
│  ──────────                                                  │
│  1.2k  ·  2.3s  ·  claude-3.5-sonnet                        │
└──────────────────────────────────────── 9:06 PM ─────────────┘
```

### Components

1. **Title Bar**: "agent" label in accent color
2. **Viewport**: Markdown-rendered content (full width)
3. **Separator**: Horizontal line before status
4. **Status Bar**: `tokens · duration · model`
5. **Subtitle**: Timestamp (bottom border)

## Design Decisions

### Border Color: Accent (Pink)
Matches the existing "agent:" label styling throughout the UI. NeXTSTEP principle: "Objects that look the same should act the same."

### Full Width Panels
Panels expand to fill the viewport rather than using fixed width. Per NeXTSTEP guidelines: "A standard window should fill a reasonable portion of the screen."

### Model in Panel, Not Top Bar
Model name moved from the top resource bar to the agent response status bar. This reduces clutter in the persistent UI while showing the model contextually with each response.

### Status Bar Metrics
Three metrics provide actionable feedback:
- **Tokens**: Cost awareness
- **Duration**: Performance awareness
- **Model**: Capability awareness

## Implementation

**File:** `src/tunacode/ui/renderers/agent_response.py`

```python
from tunacode.ui.renderers.agent_response import render_agent_response

panel = render_agent_response(
    content="Agent's markdown response...",
    tokens=1234,
    duration_ms=2340,
    model="anthropic/claude-3.5-sonnet",
)
rich_log.write(panel)
```

### Duration Tracking
Duration is tracked in `app.py:_process_request` using `time.monotonic()`:
- Start time captured before request
- Delta calculated at finalization
- Passed to renderer in milliseconds

### Model Name Formatting
Provider prefixes are stripped for cleaner display:
- `anthropic/claude-3.5-sonnet` → `claude-3.5-sonnet`
- `openai/gpt-4o` → `gpt-4o`

Long names (>20 chars) are truncated with `...`

## Resize Behavior

RichLog renders content once at write time. On terminal resize:
- New panels render at new width
- Existing panels retain original width

This is a Textual/RichLog limitation, not a bug. Accepted trade-off.

## Related Files

- `src/tunacode/ui/renderers/agent_response.py` - Panel renderer
- `src/tunacode/ui/app.py` - Integration point (lines 309-324)
- `src/tunacode/ui/widgets/resource_bar.py` - Top bar (model removed)
- `docs/ui/nextstep_panels.md` - Tool panel specification
