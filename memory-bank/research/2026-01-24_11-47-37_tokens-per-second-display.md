# Research – Agent Panel Tokens/Second Display

**Date:** 2026-01-24 11:47:37
**Owner:** tuna
**Phase:** Research
**git_commit:** b3829ebd
**last_updated:** 2026-01-24 11:47:37
**last_updated_by:** claude
**tags:** [ui, agent-panel, tokens, performance-metrics]

## Goal

Map out how to add a tokens/second display (e.g., "82 t/s") to the agent response panel, using data already available in the codebase.

## Findings

### Current Agent Panel Layout

The agent response panel is rendered in `src/tunacode/ui/renderers/agent_response.py` with the following status bar:

```
Status bar shows: model · tokens · duration
Example: "ANTH/claude-sonnet-4-5  ·  1.2k  ·  3.5s"
```

**Key files:**
- `src/tunacode/ui/renderers/agent_response.py` — Panel renderer with status bar
- `src/tunacode/ui/app.py` — Calls renderer with token/duration data

### Data Available for Tokens/Second Calculation

All required data is already tracked:

| Data | Source | Location |
|------|--------|----------|
| `completion_tokens` | `session.last_call_usage["completion_tokens"]` | `src/tunacode/ui/app.py:256` |
| `duration_ms` | `(time.monotonic() - self._request_start_time) * 1000` | `src/tunacode/ui/app.py:254` |
| `model` | `session.current_model` | `src/tunacode/ui/app.py:257` |

**Token tracking** (`src/tunacode/core/agents/agent_components/orchestrator/usage_tracker.py`):
- Tracks `prompt_tokens`, `completion_tokens`, `cached_tokens`
- Updates `session.last_call_usage` on each response
- Data flows from `NormalizedUsage` → `session.last_call_usage` → UI renderer

**Time tracking** (`src/tunacode/ui/app.py`):
- `self._request_start_time` set at request start
- `duration_ms` calculated at response completion
- Already passed to `render_agent_response()` and `render_agent_streaming()`

### Calculation

Tokens/second can be calculated as:

```python
tokens_per_second = tokens / (duration_ms / 1000)
# Or equivalently:
tokens_per_second = tokens * 1000 / duration_ms
```

Example: 1200 tokens in 3.5s → ~343 t/s → display as "343 t/s"

### Current Renderer Signatures

**`render_agent_response()`** (`src/tunacode/ui/renderers/agent_response.py:152-221`):
```python
def render_agent_response(
    content: str,
    tokens: int = 0,
    duration_ms: float = 0.0,
    model: str = "",
) -> RenderableType:
```

**`render_agent_streaming()`** (`src/tunacode/ui/renderers/agent_response.py:86-149`):
```python
def render_agent_streaming(
    content: str,
    elapsed_ms: float = 0.0,
    model: str = "",
) -> RenderableType:
```

**Note:** `render_agent_streaming()` does NOT receive `tokens` parameter. For streaming, we would need to:
1. Track current token count during streaming
2. Pass it to the renderer
3. Calculate rate from elapsed time

### Status Bar Implementation

Current status bar code (`src/tunacode/ui/renderers/agent_response.py:191-201`):

```python
status_parts = []
if model:
    status_parts.append(_format_model(model))
if tokens > 0:
    status_parts.append(_format_tokens(tokens))
if duration_ms > 0:
    status_parts.append(_format_duration(duration_ms))

status = Text()
status.append("  ·  ".join(status_parts) if status_parts else "", style=muted_color)
```

## Implementation Plan

### Step 1: Add formatting function

Add to `src/tunacode/ui/renderers/agent_response.py`:

```python
def _format_tokens_per_second(tokens: int, duration_ms: float) -> str:
    """Format tokens per second metric.

    Precondition: tokens >= 0, duration_ms > 0
    """
    if duration_ms <= 0:
        return ""
    tps = tokens * 1000 / duration_ms
    return f"{tps:.0f} t/s"
```

### Step 2: Update `render_agent_response()`

Modify status bar assembly to include tokens/second:

```python
status_parts = []
if model:
    status_parts.append(_format_model(model))
if tokens > 0 and duration_ms > 0:
    status_parts.append(_format_tokens_per_second(tokens, duration_ms))
if tokens > 0:
    status_parts.append(_format_tokens(tokens))
if duration_ms > 0:
    status_parts.append(_format_duration(duration_ms))
```

Resulting display: `"ANTH/claude-sonnet-4-5  ·  343 t/s  ·  1.2k  ·  3.5s"`

### Step 3: (Optional) Add to streaming display

For streaming, we would need to:
1. Track accumulated token count in `app.py` during streaming callback
2. Pass current token count to `render_agent_streaming()`
3. Calculate rate from elapsed time

This is more complex since we don't have true completion token count until the stream finishes. We could:
- Estimate from character count using `CHARS_PER_TOKEN = 4` from `token_counter.py`
- Or defer tokens/second to finalized response only

## References

- `src/tunacode/ui/renderers/agent_response.py` — Agent panel renderer
- `src/tunacode/ui/app.py:252-264` — Agent response rendering call site
- `src/tunacode/core/agents/agent_components/orchestrator/usage_tracker.py` — Token tracking
- `src/tunacode/utils/messaging/token_counter.py` — Token estimation utility
- `src/tunacode/core/agents/agent_components/streaming.py` — Streaming instrumentation

## Knowledge Gaps

None - all required data is available and calculation is straightforward.
