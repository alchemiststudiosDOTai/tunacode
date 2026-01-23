# Research – Streaming Watchdog Removal
**Date:** 2026-01-21
**Owner:** agent
**Phase:** Research

## Goal
Document all code, references, and dependencies for the streaming watchdog feature to enable safe removal.

## Findings

### Primary Implementation Files

| File | Lines | What to Remove |
|------|-------|----------------|
| `src/tunacode/core/agents/main.py` | 49-53 | 5 constants: `STREAM_WATCHDOG_*` |
| `src/tunacode/core/agents/main.py` | 620-639 | Function: `_coerce_stream_watchdog_timeout()` |
| `src/tunacode/core/agents/main.py` | 642-689 | Function: `_maybe_stream_node_tokens()` |
| `src/tunacode/core/agents/main.py` | 533-540 | Call site in `_run_impl()` |

### Constants to Delete (`main.py:49-53`)

```python
STREAM_WATCHDOG_DEFAULT_SECONDS: float = 20.0
STREAM_WATCHDOG_MIN_SECONDS: float = 5.0
STREAM_WATCHDOG_MAX_SECONDS: float = 45.0
STREAM_WATCHDOG_FRACTION: float = 0.25
STREAM_WATCHDOG_GLOBAL_FALLBACK: float = 120.0
```

### Functions to Delete

1. **`_coerce_stream_watchdog_timeout()`** (`main.py:620-639`)
   - Computes timeout as 25% of global request timeout
   - Clamps to 5-45 second range
   - No other callers

2. **`_maybe_stream_node_tokens()`** (`main.py:642-689`)
   - Wraps streaming with `asyncio.wait_for()` timeout
   - Falls back to non-streaming on timeout
   - Called from `_run_impl()` at line 533-540

### Call Site to Modify (`main.py:533-540`)

Current code:
```python
# Optional token streaming
await _maybe_stream_node_tokens(
    node,
    agent_run.ctx,
    self.state_manager,
    self.streaming_callback,
    ctx.request_id,
    i,
)
```

Replace with direct call to `stream_model_request_node()`:
```python
# Optional token streaming
if self.streaming_callback and Agent.is_model_request_node(node):
    await ac.stream_model_request_node(
        node,
        agent_run.ctx,
        self.state_manager,
        self.streaming_callback,
        ctx.request_id,
        i,
    )
```

### Files to Keep (No Changes Needed)

| File | Reason |
|------|--------|
| `src/tunacode/core/agents/agent_components/streaming.py` | Core streaming logic stays - only watchdog wrapper removed |
| `src/tunacode/exceptions.py` | `GlobalRequestTimeoutError` unrelated - outer timeout still exists |
| `src/tunacode/core/agents/agent_components/agent_config.py` | `_coerce_global_request_timeout()` still used by outer timeout |

### Documentation to Update

| File | Action |
|------|--------|
| `.claude/debug_history/2026-01-21_stream-hang-timeout.md` | Historical - leave as-is |
| `.claude/debug_history/2026-01-21_resume-hang-investigation.md` | Historical - leave as-is |
| `.claude/qa/raw.md` | Add removal note |
| `memory-bank/research/2026-01-21_13-48-19_abort-recovery-modularization.md` | Update reference |

### What Remains After Removal

- **Global request timeout** (`main.py:324-342`) - Outer 120s timeout via `asyncio.wait_for()` stays
- **Streaming implementation** (`streaming.py:121-411`) - `stream_model_request_node()` unchanged
- **CancelledError handling** (`streaming.py:378-393`) - Still needed for user abort (ESC)
- **Exception handling** (`streaming.py:394-410`) - Graceful degradation on stream failure stays

## Key Patterns / Solutions Found

- **Watchdog was a mitigation, not a fix**: Added 2026-01-21 to handle stream hangs
- **Root causes already fixed**: `remove_dangling_tool_calls()`, `remove_consecutive_requests()`, `remove_empty_responses()`
- **Two-tier timeout**: Inner watchdog (being removed) + outer global timeout (keeping)
- **Graceful degradation**: Falls back to non-streaming - this behavior still exists in `streaming.py` exception handlers

## Knowledge Gaps

- No tests exist for watchdog functionality (no test cleanup needed)
- Confirm streaming still works without watchdog wrapper in local testing

## Removal Checklist

1. [ ] Delete constants `STREAM_WATCHDOG_*` (lines 49-53)
2. [ ] Delete `_coerce_stream_watchdog_timeout()` (lines 620-639)
3. [ ] Delete `_maybe_stream_node_tokens()` (lines 642-689)
4. [ ] Replace call site with direct streaming call (lines 533-540)
5. [ ] Run `ruff check --fix .`
6. [ ] Test streaming manually
7. [ ] Update `.claude/qa/raw.md` with removal note

## References

- `src/tunacode/core/agents/main.py:49-53` - Constants
- `src/tunacode/core/agents/main.py:620-639` - Timeout computation
- `src/tunacode/core/agents/main.py:642-689` - Watchdog wrapper
- `src/tunacode/core/agents/main.py:533-540` - Call site
- `src/tunacode/core/agents/agent_components/streaming.py:121-411` - Streaming impl (keep)
- `.claude/debug_history/2026-01-21_stream-hang-timeout.md` - Original bug investigation
