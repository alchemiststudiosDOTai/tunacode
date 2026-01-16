# Research - Streaming Logic and UI Architecture

**Date:** 2026-01-16
**Owner:** agent
**Phase:** Research

## Goal

Map out the complete streaming architecture in tunacode, covering both core streaming logic (how LLM token deltas are captured and forwarded) and UI rendering (how streaming content is displayed progressively to users).

## Findings

### File Locations

| File | Purpose |
|------|---------|
| `src/tunacode/core/agents/agent_components/streaming.py` | Core token-level streaming from pydantic-ai |
| `src/tunacode/core/agents/main.py:350-429` | Agent orchestration, `_maybe_stream_node_tokens()` |
| `src/tunacode/ui/app.py:392-458` | UI callback, accumulation, throttling, pause/resume |
| `src/tunacode/ui/renderers/agent_response.py:86-149` | Streaming panel rendering |
| `src/tunacode/core/state.py:84-114` | Session state tracking for streaming |
| `src/tunacode/constants.py:37,187` | Streaming constants |
| `src/tunacode/ui/styles/layout.tcss:34-81` | CSS for streaming states |
| `src/tunacode/types/pydantic_ai.py` | Re-exports `PartDeltaEvent`, `TextPartDelta` |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LLM Provider (OpenAI/Anthropic/etc)                                │
│       │                                                              │
│       ▼                                                              │
│  pydantic-ai normalizes to PartDeltaEvent / TextPartDelta           │
│       │                                                              │
│       ▼                                                              │
│  streaming.py:stream_model_request_node()                           │
│       │ extracts content_delta, handles overlap detection            │
│       ▼                                                              │
│  await streaming_callback(delta_text)                               │
│       │                                                              │
│       ▼                                                              │
│  app.py:streaming_callback()                                        │
│       │ accumulates in current_stream_text                          │
│       │ throttles display updates (100ms)                           │
│       ▼                                                              │
│  app.py:_update_streaming_panel()                                   │
│       │                                                              │
│       ▼                                                              │
│  agent_response.py:render_agent_streaming()                         │
│       │ creates Rich Panel with Markdown + status bar               │
│       ▼                                                              │
│  streaming_output.update(panel)  ──► Static widget (ephemeral)      │
│                                                                      │
│  On completion:                                                      │
│  render_agent_response() ──► rich_log.write() ──► RichLog (history) │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Streaming Logic

#### 1. Agent Iteration Entry (`main.py:343-391`)

```python
async with agent.iter(self.message, message_history=message_history) as agent_run:
    async for node in agent_run:
        await _maybe_stream_node_tokens(
            node, agent_run.ctx, self.state_manager,
            self.streaming_callback, ctx.request_id, i,
        )
```

The `agent.iter()` context manager yields nodes representing model requests or tool executions.

#### 2. Stream Detection (`main.py:410-429`)

```python
async def _maybe_stream_node_tokens(node, agent_run_ctx, state_manager, streaming_cb, request_id, iteration_index):
    if not streaming_cb:
        return
    if Agent.is_model_request_node(node):
        await ac.stream_model_request_node(node, agent_run_ctx, state_manager, streaming_cb, request_id, iteration_index)
```

Only model request nodes (not tool calls) support streaming.

#### 3. Token Extraction (`streaming.py:37-277`)

**Event Loop (lines 111-268):**
```python
async with node.stream(agent_run_ctx) as request_stream:
    async for event in request_stream:
        if isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                delta_text = event.delta.content_delta or ""
                state_manager.session._debug_raw_stream_accum += delta_text
                await streaming_callback(delta_text)
```

**Overlap Detection (lines 18-34):**
```python
def _find_overlap_length(pre_text: str, delta_text: str) -> int:
    """Find longest pre_text suffix that equals delta_text prefix."""
    max_check = min(len(pre_text), len(delta_text))
    for overlap_len in range(max_check, 0, -1):
        if delta_text[:overlap_len] == pre_text[-overlap_len:]:
            return overlap_len
    return 0
```

Prevents duplicate text when models emit overlapping chunks.

**Pre-Delta Seeding (lines 186-224):**
Captures text from `PartStartEvent` before first delta to avoid visual lag. Calculates overlap and emits non-overlapping prefix.

#### 4. Graceful Degradation (`streaming.py:269-276`)

```python
except Exception as e:
    logger.warning(f"Stream failed, falling back to non-streaming: {e}")
    if hasattr(node, "_did_stream"):
        node._did_stream = False
```

### UI Rendering

#### 1. Dual-Widget Architecture

| Widget | Purpose | Lifecycle |
|--------|---------|-----------|
| `#streaming-output` (Static) | Live streaming display | Ephemeral, cleared on completion |
| `#viewport` (RichLog) | Historical message log | Permanent, receives finalized panels |

#### 2. Streaming Callback (`app.py:392-408`)

```python
async def streaming_callback(self, chunk: str) -> None:
    if self._streaming_paused:
        self._stream_buffer.append(chunk)
        return

    self.current_stream_text += chunk  # Always accumulate immediately

    now = time.monotonic()
    elapsed_ms = (now - self._last_display_update) * 1000
    if elapsed_ms >= STREAM_THROTTLE_MS:  # 100ms throttle
        self._last_display_update = now
        self._update_streaming_panel(now)
        self.streaming_output.add_class("active")
        self.rich_log.scroll_end()
```

#### 3. Panel Rendering (`agent_response.py:86-149`)

```python
def render_agent_streaming(content: str, elapsed_ms: float, model: str) -> Panel:
    # Viewport: Markdown-rendered content
    viewport = Markdown(content) if content.strip() else Text("...")

    # Status bar: model | streaming | elapsed time
    status_bar = Text()
    status_bar.append(model, style="bold")
    status_bar.append(" | streaming | ")
    status_bar.append(f"{elapsed_ms:.0f}ms")

    return Panel(
        Group(viewport, Rule(), status_bar),
        title="[primary]agent[/] [...]",
        border_style="primary",  # Blue border during streaming
    )
```

#### 4. Visual State Indicators

| State | Viewport Border | Indicator |
|-------|-----------------|-----------|
| Idle | Dim gray | None |
| Streaming | Accent (pink) | `[...]` in title, "streaming" in status |
| Paused | Warning (yellow) | "Streaming paused..." notification |

CSS classes applied via:
- `app.py:250` - Adds `streaming` class on start
- `app.py:285-286` - Removes classes on completion

#### 5. Pause/Resume (`app.py:417-441`)

**Pause:**
```python
def pause_streaming(self) -> None:
    self._streaming_paused = True
    self.query_one("#viewport").add_class(RICHLOG_CLASS_PAUSED)
```

**Resume:**
```python
def resume_streaming(self) -> None:
    self._streaming_paused = False
    self.query_one("#viewport").remove_class(RICHLOG_CLASS_PAUSED)
    if self._stream_buffer:
        self.current_stream_text += "".join(self._stream_buffer)
        self._stream_buffer.clear()
    self._update_streaming_panel(time.monotonic())
```

#### 6. Stream Completion (`app.py:282-306`)

```python
# Cleanup
self.query_one("#viewport").remove_class(RICHLOG_CLASS_STREAMING)
self.streaming_output.update("")
self.streaming_output.remove_class("active")

# Finalize to history
if self.current_stream_text and not self._streaming_cancelled:
    panel = render_agent_response(
        content=self.current_stream_text,
        tokens=tokens, duration_ms=duration_ms, model=model,
    )
    self.rich_log.write(panel, expand=True)
```

### State Management

**Session State (`state.py`):**
- `is_streaming_active: bool` - Streaming flag
- `streaming_panel: Any | None` - Active panel reference
- `_debug_raw_stream_accum: str` - Full stream for debugging
- `_debug_events: list` - Event log for diagnostics

**UI State (`app.py`):**
- `current_stream_text: str` - Accumulated display text
- `_streaming_paused: bool` - Pause flag
- `_streaming_cancelled: bool` - Cancel flag
- `_stream_buffer: list[str]` - Buffered chunks during pause
- `_last_display_update: float` - Throttle timestamp

### Configuration

| Setting | Location | Value |
|---------|----------|-------|
| Streaming enabled | `configuration/defaults.py:30` | `True` |
| Display throttle | `ui/app.py:74` | `100ms` |
| Max callback content | `constants.py:37` | `50,000 chars` |
| CSS class (streaming) | `constants.py:187` | `"streaming"` |
| CSS class (paused) | `constants.py:188` | `"paused"` |

## Key Patterns / Solutions Found

- **Callback Chain:** Single unidirectional callback passed through stack (no pub/sub)
- **Throttled Rendering:** 100ms display interval prevents UI thrashing while accumulation is immediate
- **Overlap Detection:** `_find_overlap_length()` prevents duplicate text from overlapping chunks
- **Graceful Degradation:** Stream failures reset `_did_stream` flag, allowing non-streaming fallback
- **Dual-Widget Architecture:** Separates ephemeral streaming from permanent history (NeXTSTEP principle)
- **Buffer on Pause:** Chunks queue in `_stream_buffer` during pause, flush on resume

## Knowledge Gaps

- No retry logic for failed streams (best-effort only)
- Tool results render independently during streaming (not interlaced in same panel)
- CSS styling for streaming states defined in multiple files (layout.tcss, theme-nextstep.tcss)

## References

- `src/tunacode/core/agents/agent_components/streaming.py` - Core streaming implementation
- `src/tunacode/core/agents/main.py:350-429` - Agent iteration and stream delegation
- `src/tunacode/ui/app.py:392-458` - UI callback and state management
- `src/tunacode/ui/renderers/agent_response.py:86-149` - Panel rendering
- `src/tunacode/ui/styles/layout.tcss:34-81` - CSS for streaming states
- `memory-bank/research/2026-01-14_streaming-architecture.md` - Previous streaming research
