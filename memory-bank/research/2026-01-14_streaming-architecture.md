# Research - Streaming Architecture

**Date:** 2026-01-14
**Owner:** Claude
**Phase:** Research

## Goal

Map out how the streaming system works in tunacode, from LLM token generation through UI display.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STREAMING DATA FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌─────────────────┐    ┌───────────────────────────┐  │
│  │   LLM API    │───>│   pydantic-ai   │───>│   stream_model_request_   │  │
│  │  (Provider)  │    │  agent.iter()   │    │   node()                  │  │
│  └──────────────┘    └─────────────────┘    └───────────────────────────┘  │
│                                                        │                    │
│                                                        v                    │
│                           ┌────────────────────────────────────────────┐   │
│                           │         streaming_callback(chunk)          │   │
│                           │    Callable[[str], Awaitable[None]]        │   │
│                           └────────────────────────────────────────────┘   │
│                                                        │                    │
│                                                        v                    │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        TextualReplApp                                │  │
│  │  ┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐  │  │
│  │  │ streaming_      │───>│ _update_         │───>│ Static widget  │  │  │
│  │  │ callback()      │    │ streaming_panel()│    │ (#streaming-   │  │  │
│  │  │                 │    │                  │    │  output)       │  │  │
│  │  └─────────────────┘    └──────────────────┘    └────────────────┘  │  │
│  │         │                                                            │  │
│  │         v (throttled at 100ms)                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐│  │
│  │  │ render_agent_streaming() -> Rich Panel with Markdown viewport   ││  │
│  │  └─────────────────────────────────────────────────────────────────┘│  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Findings

### Core Files

| File | Purpose |
|------|---------|
| `src/tunacode/core/agents/agent_components/streaming.py` | Token-level streaming from pydantic-ai |
| `src/tunacode/core/agents/main.py` | Orchestration, `_maybe_stream_node_tokens()` |
| `src/tunacode/ui/app.py` | UI streaming callback, throttling, display |
| `src/tunacode/ui/renderers/agent_response.py` | `render_agent_streaming()` panel |
| `src/tunacode/types/callbacks.py` | Callback type definitions |
| `src/tunacode/core/state.py` | Debug accumulator fields |

### 1. Request Initiation (`app.py:246-273`)

User submits message, UI resets streaming state and spawns async task:

```python
self.current_stream_text = ""
self._last_display_update = 0.0
self._streaming_cancelled = False
self.query_one("#viewport").add_class(RICHLOG_CLASS_STREAMING)

self._current_request_task = asyncio.create_task(
    process_request(
        message=message,
        streaming_callback=self.streaming_callback,  # <-- Key callback
        ...
    )
)
```

### 2. Agent Orchestration (`main.py:362-400`)

`RequestOrchestrator._run_impl()` uses pydantic-ai's async iteration:

```python
async with agent.iter(self.message, message_history=message_history) as agent_run:
    async for node in agent_run:
        await _maybe_stream_node_tokens(
            node, agent_run.ctx, self.state_manager,
            self.streaming_callback, ctx.request_id, i,
        )
```

### 3. Node Type Detection (`main.py:468-487`)

`_maybe_stream_node_tokens()` filters for model request nodes:

```python
if Agent.is_model_request_node(node):
    await ac.stream_model_request_node(
        node, agent_run_ctx, state_manager, streaming_cb, ...
    )
```

### 4. Token Streaming (`streaming.py:59-251`)

Core streaming loop using pydantic-ai's stream API:

```python
async with node.stream(agent_run_ctx) as request_stream:
    async for event in request_stream:
        if isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                if event.delta.content_delta is not None:
                    delta_text = event.delta.content_delta or ""
                    state_manager.session._debug_raw_stream_accum += delta_text
                    await streaming_callback(delta_text)
```

Key pydantic-ai types:
- `PartDeltaEvent` - Container event with `delta` attribute
- `TextPartDelta` - Delta with `content_delta: str` text chunk

### 5. UI Callback (`app.py:393-409`)

`streaming_callback()` accumulates text with throttled display:

```python
def streaming_callback(self, chunk: str) -> None:
    if self._streaming_paused:
        self._stream_buffer.append(chunk)
        return

    self.current_stream_text += chunk

    now = time.monotonic()
    elapsed_ms = (now - self._last_display_update) * 1000

    if elapsed_ms >= STREAM_THROTTLE_MS:  # 100ms
        self._last_display_update = now
        self._update_streaming_panel(now)
```

### 6. Panel Rendering (`app.py:411-416`, `agent_response.py:79-142`)

Updates Static widget with Rich Panel:

```python
def _update_streaming_panel(self, now: float) -> None:
    elapsed_ms = (now - self._request_start_time) * 1000
    model = self.state_manager.session.current_model or ""
    panel = render_agent_streaming(self.current_stream_text, elapsed_ms, model)
    self.streaming_output.update(panel)
```

### 7. Finalization (`app.py:301-319`)

After completion, writes permanent panel to RichLog:

```python
if self.current_stream_text and not self._streaming_cancelled:
    panel = render_agent_response(
        content=self.current_stream_text,
        tokens=tokens, duration_ms=duration_ms, model=model,
    )
    self.rich_log.write(panel, expand=True)
```

## Key Patterns / Solutions Found

### Callback Chain Pattern

```
LLM Provider
    └── pydantic-ai agent.iter() / node.stream()
        └── stream_model_request_node()
            └── streaming_callback: Callable[[str], Awaitable[None]]
                └── UI accumulation + throttled render
```

### Throttled Rendering

- `STREAM_THROTTLE_MS = 100.0` (100ms default)
- Prevents UI thrashing on fast token streams
- Accumulates all tokens, only renders periodically

### Dual Widget Architecture

| Widget | Type | Purpose |
|--------|------|---------|
| `#streaming-output` | `Static` | Live streaming display (ephemeral) |
| `#viewport` / `RichLog` | `RichLog` | Permanent scrollable history |

### Pause/Resume Buffer

```python
if self._streaming_paused:
    self._stream_buffer.append(chunk)  # Buffer while paused
    return

# On resume, flush buffer:
buffered_text = "".join(self._stream_buffer)
self.current_stream_text += buffered_text
self._stream_buffer.clear()
```

### Graceful Degradation

On streaming failure, falls back to non-streaming:

```python
except Exception as e:
    logger.warning(f"Stream failed, falling back to non-streaming: {e}")
    if hasattr(node, "_did_stream"):
        node._did_stream = False
```

### Overlap Detection

Prevents duplicate tokens when `PartStartEvent` and `PartDeltaEvent` overlap:

```python
def _find_overlap_length(pre_text: str, delta_text: str) -> int:
    for overlap_len in range(max_check, 0, -1):
        if delta_text[:overlap_len] == pre_text[-overlap_len:]:
            return overlap_len
    return 0
```

## Configuration Constants

| Constant | Value | Location |
|----------|-------|----------|
| `STREAM_THROTTLE_MS` | 100.0 | `app.py:74` |
| `RICHLOG_CLASS_STREAMING` | "streaming" | `constants.py:187` |
| `RICHLOG_CLASS_PAUSED` | "paused" | `constants.py:186` |
| `MAX_CALLBACK_CONTENT` | 50,000 | `constants.py:37` |

## CSS Styling

- `layout.tcss:34,68,78` - `#viewport.streaming` and `#streaming-output`
- `theme-nextstep.tcss:42,106,112` - NeXTSTEP theme streaming styles

## Knowledge Gaps

- How does streaming interact with tool execution? (tool calls pause streaming)
- What happens on network interruption mid-stream?
- How does local mode streaming differ (if at all)?

## References

- `src/tunacode/core/agents/agent_components/streaming.py:37-277` - Main streaming logic
- `src/tunacode/core/agents/main.py:362-487` - Orchestration
- `src/tunacode/ui/app.py:246-470` - UI streaming handling
- `src/tunacode/ui/renderers/agent_response.py:79-142` - Panel rendering
- pydantic-ai docs: `PartDeltaEvent`, `TextPartDelta` types
