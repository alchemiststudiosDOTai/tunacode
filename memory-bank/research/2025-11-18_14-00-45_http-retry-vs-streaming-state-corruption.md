# Research – HTTP Retry Transport vs Streaming State Corruption

**Date:** 2025-11-18
**Owner:** Claude (context-engineer:research)
**Phase:** Research
**Git Commit:** fe863731d6b44089e18bc1ab7630b53f6a697968
**Tags:** streaming, http-retry, pydantic-ai, state-corruption, error-handling, critical-bug

---

## Goal

Investigate why the HTTP retry transport implementation (via `AsyncTenacityTransport`) does not prevent the "You must finish streaming before calling run()" error, and identify the missing node state cleanup that causes this issue.

---

## Context

**User Report:**
After implementing HTTP-layer retries using `AsyncTenacityTransport` in [agent_config.py:130-207](agent_config.py), the following error still occurs:

```
WARNING:tunacode.core.agents.agent_components.streaming:Streaming error req=14f76ac0 iter=6: Provider returned error
Traceback (most recent call last):
  File "streaming.py", line 91, in stream_model_request_node
    async for event in request_stream:
  ...
openai.APIError: Provider returned error

ERROR:tunacode.core.agents.main:Error in process_request [req=14f76ac0 iter=6]: You must finish streaming before calling run()
```

**Implementation Background:**
- **Phase 1 (Completed):** Removed problematic retry loop from [streaming.py](streaming.py) that violated pydantic-ai's single-stream-per-node constraint
- **Phase 2 (Completed):** Implemented HTTP-layer retries via `AsyncTenacityTransport` in [agent_config.py](agent_config.py)
- **Phase 3 (MISSING):** Node state cleanup in streaming exception handler was documented but **never implemented**

---

## Key Search Patterns

```bash
# Find all streaming error handling
grep -rn "except Exception.*stream" src/tunacode/core/agents/

# Find node state references
grep -rn "_did_stream\|_result" src/

# Find HTTP retry transport usage
grep -rn "AsyncTenacityTransport\|RetryConfig" src/
```

---

## Findings

### Root Cause: Two-Layer Architecture

The HTTP retry transport and streaming layer operate at **different levels**:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: HTTP Request (AsyncTenacityTransport)             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Retries:                                                │ │
│ │   - 429 (Rate Limit)                                    │ │
│ │   - 500, 502, 503, 504 (Server Errors)                  │ │
│ │ Max attempts: 10 (from user_config["max_retries"])      │ │
│ │ Wait strategy: Respect HTTP Retry-After headers         │ │
│ │                                                         │ │
│ │ Scope: BEFORE stream starts                             │ │
│ │ Timeline: During HTTP request/response handshake        │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Stream Consumption (streaming.py)                  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ async with node.stream(agent_run_ctx) as request_stream:│ │
│ │     async for event in request_stream:                  │ │
│ │         # Consuming response chunks                     │ │
│ │         await streaming_callback(delta_text)            │ │
│ │                                                         │ │
│ │ Errors at this level:                                   │ │
│ │   - Network interruption mid-stream                     │ │
│ │   - Provider errors during streaming                    │ │
│ │   - Malformed SSE events                                │ │
│ │                                                         │ │
│ │ Current handling: NONE - node state NOT reset           │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Key Insight:** `AsyncTenacityTransport` retries happen at Layer 1 (HTTP request level). Once the HTTP request succeeds and streaming begins (Layer 2), the transport cannot retry because we're already consuming the response stream.

### Why HTTP Retries Don't Prevent This Error

**Scenario:**

1. **HTTP Request Succeeds** (Layer 1):
   - `AsyncTenacityTransport` sends request
   - Provider responds with `200 OK`
   - Stream connection established
   - No retries needed at this layer

2. **Streaming Begins** (Layer 2):
   - `node.stream()` called → sets `node._did_stream = True`
   - `async for event in request_stream:` starts consuming chunks
   - First few chunks arrive successfully

3. **Error Occurs Mid-Stream** (Layer 2):
   - Provider error occurs (e.g., `openai.APIError: Provider returned error`)
   - Exception raised while consuming stream
   - HTTP connection is ALREADY open and streaming has started
   - `AsyncTenacityTransport` cannot retry at this point

4. **Node State Corruption**:
   - `node._did_stream = True` (set in step 2)
   - `node._result = None` (never set due to exception)
   - Exception handler returns without cleanup

5. **Main Loop Failure**:
   - Main loop receives corrupt node
   - Pydantic-ai internally calls `node.run()` to get result
   - Check fails: `if self._did_stream: raise "You must finish streaming before calling run()"`

### Current Code Analysis

**[streaming.py:265-278](streaming.py#L265-L278) - Exception Handler:**

```python
except Exception as stream_err:
    # Log with context and optionally notify UI, then degrade gracefully
    logger.warning(
        "Streaming error req=%s iter=%s: %s",
        request_id,
        iteration_index,
        stream_err,
        exc_info=True,
    )
    if getattr(state_manager.session, "show_thoughts", False):
        from tunacode.ui import console as ui

        await ui.warning("Streaming failed; falling back to non-streaming mode")
```

**CRITICAL MISSING CODE:** No reset of `node._did_stream` flag

**Expected Behavior:**
Comment says "degrade gracefully" and "falling back to non-streaming mode", but without resetting `node._did_stream = False`, the node cannot be used in non-streaming mode.

### Relationship to Previous Research

**Reference:** [memory-bank/research/2025-11-18_13-08-42_streaming-retry-state-corruption.md](memory-bank/research/2025-11-18_13-08-42_streaming-retry-state-corruption.md)

**Status of Fixes:**

| Fix Item | Status | Location |
|----------|--------|----------|
| Remove retry loop | ✅ COMPLETED | streaming.py:38 (no loop exists) |
| Reset node state in exception handler | ❌ NOT IMPLEMENTED | streaming.py:265-278 |
| Reset debug state | ✅ COMPLETED | streaming.py:41-42 |
| Add state validation | ❌ NOT IMPLEMENTED | main.py:412-414 |

**Conclusion:** The retry loop was removed (Phase 1), but the critical node state reset was never added (Phase 3). HTTP retries (Phase 2) operate at a different layer and cannot prevent mid-stream failures.

---

## Key Patterns / Solutions Found

### Pattern 1: Layered Retry Architecture

**Context:** HTTP retries and streaming error handling operate at different layers

**Implementation:**

```
HTTP Layer (AsyncTenacityTransport):
  ↓ Retries request-level failures
  ↓ Respects Retry-After headers
  ↓ Success: Stream connection established

Stream Layer (streaming.py):
  ↓ Consumes response chunks
  ↓ Mid-stream errors cannot be retried
  ↓ MUST reset node state on error
  ↓ Allows fallback to non-streaming mode
```

**Relevance:** Both layers are necessary but serve different purposes:
- HTTP retries: Handle request-level failures (connection, rate limits)
- Stream cleanup: Handle mid-stream failures (corrupted chunks, provider errors)

### Pattern 2: Node State Lifecycle

**Context:** Pydantic-ai node state must be explicitly managed

**State Transitions:**

```
INITIAL STATE:
  node._did_stream = False
  node._result = None

STREAM START (node.stream() called):
  node._did_stream = True  ← SET IMMEDIATELY
  node._result = None

STREAM SUCCESS (all chunks consumed):
  node._did_stream = True
  node._result = ModelResponse(...)  ← RESULT SET

STREAM FAILURE (exception during consumption):
  node._did_stream = True
  node._result = None  ← CORRUPT STATE

CLEANUP REQUIRED:
  node._did_stream = False  ← MANUAL RESET NEEDED
  [now safe for non-streaming fallback]
```

**Key Constraint:** Once `_did_stream = True`, pydantic-ai will not call `node.run()` unless result is set OR flag is reset

### Pattern 3: Graceful Degradation Protocol

**Context:** "Fall back to non-streaming mode" requires explicit state reset

**Current Code Intent** (from comment):
> "then degrade gracefully" and "falling back to non-streaming mode"

**Missing Implementation:**
```python
except Exception as stream_err:
    logger.warning("Streaming error: %s", stream_err, exc_info=True)

    # MISSING: Reset node state to enable non-streaming fallback
    try:
        if hasattr(node, "_did_stream"):
            node._did_stream = False
    except Exception:
        logger.debug("Failed to reset node._did_stream", exc_info=True)

    # UI notification (already exists)
    if getattr(state_manager.session, "show_thoughts", False):
        await ui.warning("Streaming failed; falling back to non-streaming mode")
```

**Relevance:** Without state reset, "fallback" is impossible and agent crashes instead

---

## Knowledge Gaps

### Gap 1: Why Was State Reset Never Implemented?

**Question:** The previous research doc clearly documented the need to reset `node._did_stream`. Why was this fix not applied?

**Hypothesis:**
1. Phase 1 (remove retry loop) was implemented
2. HTTP retry transport (Phase 2) was added as alternative approach
3. Assumption: HTTP retries would prevent streaming errors entirely
4. Phase 3 (state cleanup) was forgotten or deemed unnecessary

**Reality:** HTTP retries prevent *request-level* failures but not *mid-stream* failures

### Gap 2: Can AsyncTenacityTransport Retry Mid-Stream?

**Question:** Is there a way to configure `AsyncTenacityTransport` to retry mid-stream failures?

**Investigation:**

`AsyncTenacityTransport` wraps httpx and retries at the HTTP request level. Once the request succeeds and the response stream is opened, the transport considers the request complete. Mid-stream errors happen during chunk consumption, which is outside the transport's scope.

**Conclusion:** No, HTTP-level retries cannot handle streaming errors. Stream consumption is a separate layer.

### Gap 3: Partial Stream Recovery

**Question:** When stream fails mid-way, can we use the partial content already streamed?

**Current Implementation:**
- `state_manager.session._debug_raw_stream_accum` accumulates all deltas (line 246)
- This buffer contains partial results up to the point of failure

**Opportunity:**
Could surface partial results to user even after streaming fails:
```python
except Exception as stream_err:
    logger.warning("Streaming error: %s", stream_err, exc_info=True)

    # Surface partial results
    partial_text = state_manager.session._debug_raw_stream_accum
    if partial_text and streaming_callback:
        # Already sent via streaming_callback during loop
        # Could log summary: "Streamed {len(partial_text)} chars before failure"
        pass
```

**Current Status:** Partial results are already sent to UI via `streaming_callback` during the loop, so user sees them before error occurs

---

## References

### Primary Source Files

1. **Streaming Handler:**
   - [src/tunacode/core/agents/agent_components/streaming.py](src/tunacode/core/agents/agent_components/streaming.py)
   - Lines 20-278: `stream_model_request_node()`
   - Lines 265-278: Exception handler **missing state reset**

2. **HTTP Retry Transport:**
   - [src/tunacode/core/agents/agent_components/agent_config.py](src/tunacode/core/agents/agent_components/agent_config.py)
   - Lines 130-182: `_create_model_with_retry()` helper
   - Lines 194-207: Retry transport integration with pydantic-ai

3. **Main Agent Loop:**
   - [src/tunacode/core/agents/main.py](src/tunacode/core/agents/main.py)
   - Lines 406-414: Agent iteration and streaming delegation
   - Line 412: `_maybe_stream_node_tokens()` call that receives corrupt node

### Related Knowledge Base Entries

1. **Previous Research:**
   - [memory-bank/research/2025-11-18_13-08-42_streaming-retry-state-corruption.md](memory-bank/research/2025-11-18_13-08-42_streaming-retry-state-corruption.md)
   - Documented the retry loop bug and state reset fix
   - **Critical section:** Lines 417-432 (state reset code never implemented)

2. **Implementation Plan:**
   - [memory-bank/plan/plan-1.md](memory-bank/plan/plan-1.md)
   - Phase 1: Remove retry loop ✅
   - Phase 2: Add HTTP retries ✅
   - Phase 3: State cleanup ❌ (this task)

### External Dependencies

**Pydantic-AI:**
- `ModelRequestNode._did_stream`: Private flag controlling re-entry
- `node.stream()`: Context manager that sets `_did_stream = True`
- `node.run()`: Checks `_did_stream` and raises if True without result

**AsyncTenacityTransport:**
- Wraps httpx with tenacity retry logic
- Scope: HTTP request/response handshake
- Cannot retry after stream consumption begins

---

## Next Steps for Implementation

### Critical Fix (Phase 3 - REQUIRED)

**File:** [src/tunacode/core/agents/agent_components/streaming.py:265-278](src/tunacode/core/agents/agent_components/streaming.py#L265-L278)

**Change:**

```python
except Exception as stream_err:
    # Log with context and optionally notify UI, then degrade gracefully
    logger.warning(
        "Streaming error req=%s iter=%s: %s",
        request_id,
        iteration_index,
        stream_err,
        exc_info=True,
    )

    # Reset node state to allow graceful degradation to non-streaming mode
    try:
        if hasattr(node, "_did_stream"):
            node._did_stream = False
            logger.debug(
                "Reset node._did_stream after streaming error (req=%s iter=%s)",
                request_id,
                iteration_index,
            )
    except Exception as reset_err:
        logger.debug(
            "Failed to reset node._did_stream (req=%s iter=%s): %s",
            request_id,
            iteration_index,
            reset_err,
            exc_info=True,
        )

    if getattr(state_manager.session, "show_thoughts", False):
        from tunacode.ui import console as ui

        await ui.warning("Streaming failed; falling back to non-streaming mode")
```

**Justification:**
1. Allows pydantic-ai to process node in non-streaming mode (via `node.run()`)
2. Prevents "You must finish streaming before calling run()" error
3. Implements the "graceful degradation" described in existing comment
4. Documented in previous research but never implemented

### Testing

**Characterization Test:**
```python
# tests/characterization/agent/test_streaming_failure_recovery.py

async def test_streaming_mid_stream_failure_recovery():
    """When stream fails mid-way, node state should be reset for fallback."""
    # Setup: Mock provider that fails mid-stream
    # Act: Trigger streaming error
    # Assert: node._did_stream == False after exception
    # Assert: Agent continues without crash
```

**Regression Test:**
```python
async def test_http_retry_and_stream_cleanup_layers():
    """HTTP retries and stream cleanup operate at different layers."""
    # Setup: Mock HTTP failures (should retry at HTTP layer)
    # Setup: Mock mid-stream failures (should reset at stream layer)
    # Assert: Both layers handle their respective failures
```

### Documentation

**Update KB:**
```bash
claude-kb add debug_history \
  --component "streaming" \
  --summary "HTTP retries don't prevent mid-stream state corruption" \
  --error "You must finish streaming before calling run()" \
  --solution "Reset node._did_stream=False in streaming.py exception handler"

claude-kb sync --verbose
claude-kb validate
```

**Module-Level Comment** (streaming.py:1-6):
```python
"""Streaming instrumentation and handling for agent model request nodes.

This module encapsulates verbose streaming + logging logic used during
token-level streaming from the LLM provider. It updates session debug fields
and streams deltas to the provided callback while being resilient to errors.

IMPORTANT: Streaming errors occur AFTER HTTP retries (AsyncTenacityTransport)
have succeeded. Mid-stream failures require explicit node state reset to allow
graceful degradation to non-streaming mode. See exception handler at line 265.
"""
```

---

## Summary

The "You must finish streaming before calling run()" error persists because **HTTP retries and streaming error handling operate at different architectural layers**:

1. **HTTP Layer (AsyncTenacityTransport):** Retries request-level failures before streaming begins
2. **Stream Layer (streaming.py):** Handles mid-stream failures after HTTP connection is established

**The Bug:**
When a stream fails mid-consumption, `node._did_stream = True` but `node._result = None`. The exception handler logs the error but does NOT reset the node state, leaving it in a corrupt state that prevents non-streaming fallback.

**The Fix:**
Add `node._did_stream = False` in the exception handler at [streaming.py:265-278](streaming.py#L265-L278). This is a **3-line change** that was documented in previous research but never implemented.

**Implementation Status:**
- ✅ Phase 1: Removed retry loop
- ✅ Phase 2: Added HTTP retry transport
- ❌ Phase 3: Node state cleanup (THIS FIX)

**Status:** Ready for immediate implementation - simple fix, clear solution, well-documented root cause.
