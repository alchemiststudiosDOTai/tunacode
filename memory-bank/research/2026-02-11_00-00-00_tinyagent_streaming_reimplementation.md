# Research – Re-implementing Streaming with tinyagent

**Date:** 2026-02-11
**Owner:** claude
**Phase:** Research
**git_commit:** 00f2bd6b653737664499363a01e871a00bf51342
**branch:** master

---

## Goal

Understand the current state of streaming in the tinyagent-based codebase and identify what is needed to bring back streaming support that was removed during the pydantic-ai to tinyagent migration.

---

## Executive Summary

**Streaming is currently DISABLED but the infrastructure is largely intact.**

The core agent loop (`src/tunacode/core/agents/main.py`) already consumes tinyagent's `agent.stream()` and handles `text_delta` events. However, the UI layer passes `streaming_callback=None`, effectively disabling real-time streaming display. To re-enable streaming, the primary work needed is in the UI layer to:

1. Create a streaming callback that updates the UI incrementally
2. Potentially restore throttled display updates for performance
3. Handle streaming panel lifecycle (start, update, end)

---

## Findings

### 1. Current Architecture (Streaming EXISTS but is DISABLED)

#### Core Streaming Infrastructure (ALREADY WORKING)

**File:** `src/tunacode/core/agents/main.py:670-748`

The `RequestOrchestrator._run_stream()` method already iterates over tinyagent events:

```python
async for event in agent.stream(self.message):
    ev_type = getattr(event, "type", None)
    # ... dispatches to handlers
```

The `_handle_message_update()` method (lines 728-748) extracts text deltas and would call the streaming callback if one were provided:

```python
async def _handle_message_update(self, event: Any) -> None:
    if not self.streaming_callback:
        return  # <-- Early exit because callback is None

    assistant_event = getattr(event, "assistant_message_event", None)
    if assistant_event.get("type") != "text_delta":
        return

    delta = assistant_event.get("delta")
    await self.streaming_callback(delta)  # <-- Would stream here
```

#### UI Layer (STREAMING DISABLED)

**File:** `src/tunacode/ui/app.py:214`

The `process_request()` call explicitly passes `streaming_callback=None`:

```python
self._current_request_task = asyncio.create_task(
    process_request(
        message=message,
        model=ModelName(model_name),
        state_manager=self.state_manager,
        tool_callback=build_textual_tool_callback(),
        streaming_callback=None,  # <-- DISABLED
        tool_result_callback=build_tool_result_callback(self),
        tool_start_callback=build_tool_start_callback(self),
        notice_callback=self._show_system_notice,
        compaction_status_callback=self._update_compaction_status,
    )
)
```

---

### 2. tinyagent Streaming API (Ready to Use)

**tinyagent** has native, first-class streaming support via `agent.stream()`:

#### Event Types from `agent.stream()`

| Event Type | Purpose | Relevant for Streaming Display |
|------------|---------|-------------------------------|
| `agent_start` | Agent run begins | Show loading state |
| `message_start` | Message streaming starts | Initialize streaming panel |
| `message_update` | Message content updated | **Update streaming text** |
| `message_end` | Message streaming complete | Finalize, show metadata |
| `tool_execution_start` | Tool execution begins | Show tool panel |
| `tool_execution_end` | Tool execution complete | Update tool panel status |
| `turn_end` | Turn ends | Check iteration limits |
| `agent_end` | Agent run ends | Cleanup |

#### Text Delta Extraction

**File:** `tinyagent/agent_loop.py:171-207`

The low-level `AssistantMessageEvent` types include:
- `text_delta` - Individual token chunks
- `text_start` / `text_end` - Text block boundaries
- `thinking_delta` - Reasoning content (for models like Claude)

The `stream_text()` helper method (tinyagent) extracts just text deltas:

```python
async for text_delta in agent.stream_text("Hello"):
    print(text_delta, end="")  # Just the text deltas
```

---

### 3. What Was Removed (Historical Context)

During the pydantic-ai to tinyagent migration, significant streaming UI infrastructure was removed:

#### Deleted Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/tunacode/core/agents/agent_components/streaming.py` | 302 | pydantic-ai specific streaming orchestration |
| `src/tunacode/core/agents/agent_components/streaming_debug.py` | 372 | Debug helpers for streaming events |

#### Removed UI Features (from `app.py`)

| Feature | Description | Potential Value |
|---------|-------------|-----------------|
| `streaming_callback(chunk: str)` | Received token chunks | **Essential** - core callback |
| `_update_streaming_panel()` | Updated UI with streaming content | **Essential** - UI update |
| `STREAM_THROTTLE_MS = 100.0` | Throttle display updates | **Recommended** - performance |
| `_stream_buffer: list[str]` | Buffer for paused streaming | Optional - nice to have |
| `action_toggle_pause()` | Pause/resume streaming | Optional - nice to have |
| `action_cancel_stream()` | Cancel streaming | Already handled via abort |

#### Removed ChatContainer Methods

```python
# From chat.py - managed streaming widget lifecycle
def start_stream(self, initial_content=None) -> Widget
def update_stream(self, renderable) -> None
def end_stream(self) -> None
def cancel_stream(self) -> None
def insert_before_stream(self, renderable) -> Widget  # Tool panel positioning
```

---

### 4. Current UI Infrastructure (Can Be Leveraged)

#### Existing Streaming Widget

**File:** `src/tunacode/ui/app.py:99,104`

```python
self.streaming_output: Static  # Declaration at line 99
self.streaming_output = Static("", id="streaming-output")  # Initialization at line 104
```

The widget exists and is cleared after each request (lines 232-233), but **nothing writes to it during streaming**.

#### CSS for Streaming Output

**File:** `src/tunacode/ui/styles/layout.tcss:68-81`

```tcss
#streaming-output {
    display: none;
    height: auto;
    max-height: 50%;
    dock: bottom;
}

#streaming-output.active {
    display: block;
}
```

The CSS already supports showing/hiding the streaming output with the `active` class.

#### Callback Type Definition

**File:** `src/tunacode/types/callbacks.py:70`

```python
StreamingCallback: TypeAlias = Callable[[str], Awaitable[None]]
```

The type signature is already defined and imported in all the right places.

---

### 5. Re-implementation Plan

Based on the research, here's the minimal work needed to restore streaming:

#### Phase 1: Basic Streaming (MVP)

1. **Create streaming callback in `app.py`** (lines ~200-220)
   - Accumulate text chunks
   - Update `self.streaming_output` widget
   - Add `active` class to show the panel

2. **Pass the callback to `process_request()`** (line 214)
   - Change `streaming_callback=None` to `streaming_callback=self._streaming_callback`

3. **Handle streaming completion** (in finally block ~line 232)
   - Clear streaming output
   - Remove `active` class
   - Render final response to chat container (already happening)

#### Phase 2: Polish (Recommended)

4. **Add throttled updates**
   - Add `STREAM_THROTTLE_MS = 100.0` constant
   - Track last update time
   - Only update UI every 100ms to reduce visual churn

5. **Add streaming panel styling**
   - Create `render_agent_streaming()` in `agent_response.py`
   - Show elapsed time, model name
   - Use NeXTSTEP panel styling

#### Phase 3: Advanced (Optional)

6. **Pause/Resume support**
   - Add `_streaming_paused` flag
   - Add `_stream_buffer` for paused chunks
   - Implement keyboard shortcuts

7. **Tool panel anchoring**
   - Restore `insert_before_stream()` functionality
   - Ensures tool panels appear in correct chronological position

---

## Key Patterns / Solutions Found

### Pattern 1: Dual-Display System (Historical)

The previous implementation used a dual-display approach:

1. **Streaming Phase:** Content appears in `#streaming-output` overlay (fixed position)
2. **Final Phase:** Content is moved to `rich_log` as permanent panel

**Rationale:** Prevents scroll jitter in RichLog during active generation.

### Pattern 2: Throttled Updates (Historical)

```python
STREAM_THROTTLE_MS: float = 100.0

async def streaming_callback(self, chunk: str) -> None:
    self.current_stream_text += chunk  # Always accumulate

    now = time.monotonic()
    elapsed_ms = (now - self._last_display_update) * 1000

    if elapsed_ms >= STREAM_THROTTLE_MS:
        self._last_display_update = now
        self._update_streaming_panel()
```

**Rationale:** Reduces markdown re-renders and visual churn.

### Pattern 3: Event-Based Streaming (Current - tinyagent)

```python
# Current implementation in main.py:693
async for event in agent.stream(self.message):
    ev_type = getattr(event, "type", None)
    handler = handlers.get(ev_type)
    if handler:
        should_stop = await handler(event, ...)
```

**Rationale:** Clean separation between agent loop and UI concerns.

---

## Knowledge Gaps

1. **Markdown rendering during streaming:** How should partial markdown be rendered? (Previous implementation likely used Rich's markdown with partial content)

2. **Error handling during streaming:** What happens if the streaming callback raises an exception?

3. **CSS styling:** Does the current CSS properly style the streaming output panel, or does it need updates?

4. **Accessibility:** Are there screen reader considerations for streaming content?

---

## References

### Code References

| File | Lines | Purpose |
|------|-------|---------|
| `src/tunacode/core/agents/main.py` | 670-748 | `_run_stream()` and `_handle_message_update()` |
| `src/tunacode/core/agents/main.py` | 728-748 | Streaming callback invocation |
| `src/tunacode/ui/app.py` | 214 | `streaming_callback=None` (disabled) |
| `src/tunacode/ui/app.py` | 99, 104 | `streaming_output` widget declaration |
| `src/tunacode/ui/app.py` | 232-233 | Streaming cleanup in finally block |
| `src/tunacode/types/callbacks.py` | 70 | `StreamingCallback` type definition |
| `src/tunacode/ui/styles/layout.tcss` | 68-81 | `#streaming-output` CSS |

### Historical Research

- `memory-bank/research/2026-01-27_16-11-11_streaming_and_panels.md` - Previous streaming architecture
- `memory-bank/research/2026-02-09_11-33-09_pydantic-ai_to_tinyagent_migration_and_recent_changes.md` - Migration details
- `.claude/delta/2026-02-07_remove-orchestrator-tool-dispatcher.md` - Orchestrator removal

### tinyagent Source

- `.venv/lib/python3.12/site-packages/tinyagent/agent.py:487-533` - `Agent.stream()` method
- `.venv/lib/python3.12/site-packages/tinyagent/agent_loop.py:359-396` - `agent_loop()` function
- `.venv/lib/python3.12/site-packages/tinyagent/agent_types.py:309-388` - Agent event types

### Git History

- `ec875418` - "nukink streaming to clean up codebase" (Jan 29, 2026)
- `743355aa` - "Phase 5: delete remaining legacy pydantic-ai shims" (Feb 7, 2026)
- `ab49b841` - "refactor: reduce request/streaming complexity" (Jan 31, 2026)

---

## Next Steps

1. **Create implementation plan** in `memory-bank/plan/`
2. **Implement Phase 1** (basic streaming) - minimal changes to `app.py`
3. **Test with small model requests** to verify token-level streaming works
4. **Implement Phase 2** (throttling, styling) based on user feedback
