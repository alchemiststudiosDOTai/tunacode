# Research – Streaming Retry State Corruption and Node Lifecycle Bug

**Date:** 2025-11-18
**Owner:** Claude (context-engineer:research)
**Phase:** Research
**Git Commit:** 3333c1c0bc3e8d8e963aa37a3d249e4e0fe80163
**Tags:** streaming, error-handling, pydantic-ai, node-lifecycle, state-corruption, critical-bug

---

## Goal

Map the streaming retry logic bug where `node.stream()` is called multiple times, causing:
1. `AssertionError: stream() should only be called once per node`
2. Process state corruption leading to `You must finish streaming before calling run()`
3. Agent crash when LLM provider returns errors during streaming

This research documents the root cause, affected components, and architectural constraints before implementing fixes.

---

## Error Scenario

**User Report:**
> When an `openai.APIError` (Provider returned error) occurs during streaming, the retry logic in `stream_model_request_node` attempts to call `node.stream()` a second time. Pydantic_ai nodes do not support multiple stream attempts, causing `AssertionError: stream() should only be called once per node`. The unhandled streaming failure leaves the agent loop in an inconsistent state, leading to `You must finish streaming before calling run()`.

**Affected Files:**
- `src/tunacode/core/agents/agent_components/streaming.py` (lines 38-40: retry loop)
- `src/tunacode/core/agents/main.py` (line 412: process_request loop crash point)

---

## Key Search Patterns

For further investigation:
```bash
# Find all streaming-related code
grep -ri "node.stream" src/

# Find pydantic_ai node usage
grep -ri "_did_stream\|ModelRequestNode" src/

# Find error handling around streaming
grep -ri "stream.*except\|streaming.*error" src/
```

Additional context:
```bash
# Check knowledge base for prior streaming issues
grep -ri "stream\|retry" .claude/
```

---

## Findings

### Core Architecture

**Call Stack:**
```
main.py:406-408       → Agent iteration loop yields nodes
    ↓
main.py:412-414       → _maybe_stream_node_tokens() delegates to streaming handler
    ↓
streaming.py:20-290   → stream_model_request_node() implements retry logic
    ↓
streaming.py:38-40    → for attempt in range(2): PROBLEMATIC RETRY
    ↓
streaming.py:40       → async with node.stream(agent_run_ctx): FIRST CALL
    ↓
[EXCEPTION OCCURS]    → openai.APIError or similar provider error
    ↓
streaming.py:268-289  → Exception handler catches error
    ↓
[RETRY ATTEMPT]       → Loop continues to second iteration
    ↓
streaming.py:40       → async with node.stream(agent_run_ctx): SECOND CALL
    ↓
[ASSERTION ERROR]     → Pydantic_ai raises "stream() should only be called once per node"
```

### Relevant Files and Their Roles

**Streaming Implementation:**
- [`src/tunacode/core/agents/agent_components/streaming.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/3333c1c0bc3e8d8e963aa37a3d249e4e0fe80163/src/tunacode/core/agents/agent_components/streaming.py#L20-L290)
  - `stream_model_request_node()`: Main streaming handler with **problematic retry logic**
  - Lines 38-40: `for attempt in range(2)` retry loop that violates pydantic_ai constraints
  - Lines 268-289: Exception handler that **does not reset node state**

**Agent Loop Management:**
- [`src/tunacode/core/agents/main.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/3333c1c0bc3e8d8e963aa37a3d249e4e0fe80163/src/tunacode/core/agents/main.py#L372-L538)
  - `process_request()`: Main entry point (line 372)
  - Lines 406-414: Agent iteration loop that yields nodes and delegates streaming
  - Line 412: `_maybe_stream_node_tokens()` - crashes here when streaming state is corrupted
  - Line 417: `_process_node()` - receives corrupted node after streaming failure

**State Management:**
- `src/tunacode/core/state.py`: Global state manager
- `src/tunacode/core/agents/agent_components/response_state.py`: Response-level state tracking
- `src/tunacode/core/agents/agent_components/node_processor.py`: Node lifecycle management

**Error Handling:**
- `src/tunacode/exceptions.py`: Custom exception definitions
- `src/tunacode/utils/retry.py`: Retry logic utilities
- `src/tunacode/cli/repl_components/error_recovery.py`: REPL-level error recovery

### Pydantic_AI Node Lifecycle Constraints

**Critical Constraint:** Each `ModelRequestNode` can only be streamed **once**. This is enforced by:

1. **Internal Flag:** `node._did_stream` is set to `True` when `node.stream()` is called
2. **Assertion Check:** Pydantic_ai checks `assert not self._did_stream` before allowing stream
3. **No Reset Mechanism:** Once `_did_stream = True`, it cannot be reset (immutable design)
4. **One-Time Use:** Nodes represent a single LLM request/response pair, not replayable

**Node State Transitions:**

```
BEFORE first stream():
  node._did_stream = False
  node._result = None

DURING stream() context manager entry:
  node._did_stream = True  ← SET IMMEDIATELY

IF streaming succeeds:
  node._result = ModelResponse(...)
  Context manager exits cleanly

IF streaming fails with exception:
  node._result = None       ← NOT SET
  node._did_stream = True   ← STILL TRUE (CANNOT BE RESET)
  Context manager __aexit__ runs
  Exception propagates to tunacode handler

AFTER exception in tunacode:
  node._did_stream = True   ← CORRUPT STATE
  node._result = None       ← CORRUPT STATE
  [NO CLEANUP IN CURRENT CODE]

When retry attempts node.stream() again:
  Pydantic_ai checks: assert not self._did_stream
  FAILS → AssertionError: stream() should only be called once per node
```

### The Problematic Retry Pattern

**Current Implementation** ([`streaming.py:38-289`](https://github.com/alchemiststudiosDOTai/tunacode/blob/3333c1c0bc3e8d8e963aa37a3d249e4e0fe80163/src/tunacode/core/agents/agent_components/streaming.py#L38-L289)):

```python
for attempt in range(2):  # attempt = 0, 1
    try:
        async with node.stream(agent_run_ctx) as request_stream:
            # Stream processing (lines 41-265)
            async for event in request_stream:
                # ... handle deltas ...
                await streaming_callback(delta_text)

        # Success: exit retry loop
        break

    except Exception as stream_err:
        # Log error (lines 270-276)
        logger.warning("Streaming error (attempt %s/2) ...", attempt + 1, stream_err)

        # Show UI warning (lines 278-281)
        await ui.warning("Streaming failed; retrying once then falling back")

        # CRITICAL BUG: No state reset here!
        # On first failure (attempt=0), loop continues to attempt=1
        # Line 40 executes AGAIN with same corrupted node
        # Pydantic_ai raises AssertionError

        # Only break on SECOND failure
        if attempt == 1:
            await ui.muted("Switching to non-streaming processing for this node")
            break
```

**Why This Fails:**

1. **First Attempt (attempt=0):**
   - `node.stream()` called → `node._did_stream = True`
   - Provider error occurs (e.g., `openai.APIError`)
   - Exception caught at line 268
   - **No `break` statement** → loop continues

2. **Second Attempt (attempt=1):**
   - Loop iterates to line 40 again
   - Attempts `node.stream()` on **same node object**
   - Pydantic_ai checks `node._did_stream == True`
   - **Raises AssertionError** before entering context manager

3. **State Corruption:**
   - Even if retry somehow proceeds, `node._did_stream=True` + `node._result=None`
   - Main loop at `main.py:408` continues with corrupted node
   - When pydantic_ai tries to call `node.run()` internally
   - **Fatal check fails:** "You must finish streaming before calling run()"

### Process State Corruption Details

**How State Gets Corrupted:**

When streaming fails and the retry loop exits at line 289 (`break`), the node is returned to the main agent loop with:

```python
node._did_stream = True   # Indicates streaming was attempted
node._result = None       # No result because streaming failed
```

**What Happens Next in Main Loop:**

```python
# main.py:408 - Agent loop continues
async for node in agent_run:
    # line 412: Streaming already failed, but node is corrupt
    await _maybe_stream_node_tokens(node, ...)

    # line 417: Node processing attempts to use the corrupt node
    await ac._process_node(node, ...)
```

**When Pydantic_AI Detects Corruption:**

Internally, pydantic_ai's graph processor calls `node.run()` to get the final result. The check:

```python
# In pydantic_ai's ModelRequestNode.run() method
if self._did_stream:
    raise exceptions.AgentRunError(
        'You must finish streaming before calling run()'
    )
```

This error occurs because:
- `_did_stream=True` signals that streaming was initiated
- `_result=None` signals that streaming didn't complete
- Pydantic_ai expects either:
  - Streaming completed: `_did_stream=True` + `_result=set`
  - No streaming: `_did_stream=False` + call `run()` instead

The current code leaves node in invalid middle state.

### Session Debug State Corruption

**Additional Problem:** Session state mutations are unprotected

Lines that mutate session state during streaming:
- Line 42: `state_manager.session._debug_raw_stream_accum = ""`
- Line 43: `state_manager.session._debug_events = []`
- Line 86-90: Appends to `_debug_events`
- Line 247: Concatenates to `_debug_raw_stream_accum`

**Issue:** If retry occurs:
- First attempt populates debug state
- Exception occurs, debug state partially filled
- Second attempt **appends to corrupted debug state**
- Result: misleading debug output with mixed data from both attempts

**No protection via:**
- Locks
- Atomic operations
- State reset between retry attempts

---

## Key Patterns / Solutions Found

### Pattern 1: Single-Stream Guarantee (Pydantic_AI Design)

**Context:** Pydantic_ai enforces single-stream-per-node via `_did_stream` flag

**Implication:** Retry logic **cannot** call `node.stream()` twice on same node

**Solution Approaches:**
1. **Remove retry entirely** - Accept single attempt, degrade gracefully on failure
2. **Reset node state** - Explicitly set `node._did_stream = False` after failure
3. **Create new node** - Obtain fresh node object for retry (not possible, nodes come from iterator)

### Pattern 2: Graceful Degradation on Streaming Failure

**Current Intent:** Lines 284-289 attempt to "degrade gracefully" to non-streaming

**What's Missing:** No cleanup to enable degradation

**Required Fix:**
```python
except Exception as stream_err:
    logger.warning("Streaming error: %s", stream_err, exc_info=True)

    # FIX: Reset node state to allow non-streaming path
    try:
        if hasattr(node, "_did_stream"):
            node._did_stream = False
    except Exception:
        logger.debug("Failed to reset node state", exc_info=True)

    # Now safe to break and let node processing continue without streaming
    break
```

### Pattern 3: Context Manager Cleanup Assumptions

**Assumption in Current Code:** Context manager `__aexit__` will clean up state

**Reality:** `__aexit__` runs, but `_did_stream` flag persists

**Lesson:** Cannot rely on context manager to reset flags that prevent re-entry

---

## Knowledge Gaps

### Gap 1: Pydantic_AI Internal Node Reset Protocol

**Question:** Does pydantic_ai provide an official way to reset `_did_stream`?

**Investigation Needed:**
- Check pydantic_ai documentation for node lifecycle management
- Search for `reset()` or `clear()` methods on `ModelRequestNode`
- Review pydantic_ai source code for intended error recovery patterns

**Workaround:** Direct mutation `node._did_stream = False` (accessing private attribute)

### Gap 2: Partial Stream Consumption Recovery

**Question:** When streaming fails mid-iteration, are partial results available?

**Current State:** Lines 247-248 accumulate deltas in `_debug_raw_stream_accum`

**Opportunity:** Could surface partial stream results to user even after failure

**Investigation Needed:**
- Can we extract `_debug_raw_stream_accum` and use it as fallback output?
- What quality guarantees exist for partial streams?

### Gap 3: Provider Error Classification

**Question:** Which provider errors should trigger retry vs immediate degradation?

**Current Code:** Retries ALL exceptions (line 268: `except Exception as stream_err`)

**Better Approach:**
- Retry: Transient errors (timeout, rate limit)
- No retry: Auth errors, invalid requests
- Requires classifying `openai.APIError` subtypes

### Gap 4: Testing Strategy for Streaming Failures

**Question:** How to reliably test streaming failure scenarios?

**Needed:**
- Mock provider that raises errors mid-stream
- Characterization test for node state after failure
- Regression test for "You must finish streaming before calling run()" bug

**Current Tests:**
- No evidence of streaming failure tests in search results
- `tests/characterization/repl/test_error_handling.py` exists but scope unclear

---

## References

### Primary Source Files

1. **Streaming Handler:**
   - [`src/tunacode/core/agents/agent_components/streaming.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/3333c1c0bc3e8d8e963aa37a3d249e4e0fe80163/src/tunacode/core/agents/agent_components/streaming.py)
   - Lines 20-290: `stream_model_request_node()`
   - Lines 38-40: Problematic retry loop
   - Lines 268-289: Exception handler missing state reset

2. **Main Agent Loop:**
   - [`src/tunacode/core/agents/main.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/3333c1c0bc3e8d8e963aa37a3d249e4e0fe80163/src/tunacode/core/agents/main.py)
   - Lines 372-538: `process_request()`
   - Lines 406-414: Agent iteration and streaming delegation
   - Line 158: `Agent.is_model_request_node(node)` check

3. **Node Processing:**
   - `src/tunacode/core/agents/agent_components/node_processor.py`
   - Handles node lifecycle after streaming completes/fails

### Related Knowledge Base Entries

**Prior Streaming Research:**
- `.claude/development/esc-investigation/ESC_KEY_STREAMING_ANALYSIS.md`
  - Recent analysis of multiple stream call issues
  - Related to ESC key handling during streaming

**Error Handling Documentation:**
- `memory-bank/research/2025-09-12_12-15-48_global_graceful_error_handling_analysis.md`
  - Global error handling strategy analysis

**Architecture Maps:**
- `memory-bank/research/2025-11-16_main-agent-architecture-map.md`
  - Main agent architecture documentation
- `.claude/semantic_index/function_call_graphs.json`
  - Call graph showing process_request → streaming relationships

### External Dependencies

**Pydantic_AI:**
- `ModelRequestNode` class: Enforces single-stream constraint
- `_did_stream` flag: Private attribute controlling stream re-entry
- `node.stream()` method: Returns async context manager for streaming
- `node.run()` method: Fallback for non-streaming execution

**Provider Libraries:**
- `openai.APIError`: Exception type from OpenAI provider
- Various provider-specific error types (needs classification)

---

## Next Steps for Implementation

### Critical Fixes (Required Before Debugging)

1. **Add Node State Reset in Exception Handler** ([`streaming.py:268-289`](https://github.com/alchemiststudiosDOTai/tunacode/blob/3333c1c0bc3e8d8e963aa37a3d249e4e0fe80163/src/tunacode/core/agents/agent_components/streaming.py#L268-L289))
   ```python
   except Exception as stream_err:
       logger.warning("Streaming error: %s", stream_err, exc_info=True)

       # Reset node state to allow graceful degradation
       try:
           if hasattr(node, "_did_stream"):
               node._did_stream = False
       except Exception:
           logger.debug("Failed to reset node._did_stream", exc_info=True)

       # Break immediately - no retry on same node
       break
   ```

2. **Remove Retry Loop** ([`streaming.py:38`](https://github.com/alchemiststudiosDOTai/tunacode/blob/3333c1c0bc3e8d8e963aa37a3d249e4e0fe80163/src/tunacode/core/agents/agent_components/streaming.py#L38))
   - Change `for attempt in range(2):` to single try/except
   - Document that streaming is single-attempt only
   - Rely on graceful degradation instead of retry

3. **Reset Debug State** ([`streaming.py:42-43`](https://github.com/alchemiststudiosDOTai/tunacode/blob/3333c1c0bc3e8d8e963aa37a3d249e4e0fe80163/src/tunacode/core/agents/agent_components/streaming.py#L42-L43))
   ```python
   # Always start with clean debug state
   state_manager.session._debug_raw_stream_accum = ""
   state_manager.session._debug_events = []
   ```

### High-Priority Improvements

4. **Add Streaming State Validation** (`main.py:412-420`)
   - After `_maybe_stream_node_tokens()` returns, validate node state
   - Log warnings if `_did_stream=True` but `_result=None`
   - Provides early detection of corruption

5. **Classify Provider Errors**
   - Distinguish transient vs permanent errors
   - Only retry transient errors (if retry is re-introduced later)
   - Document error handling strategy

### Documentation

6. **Add Module-Level Documentation** ([`streaming.py:1-6`](https://github.com/alchemiststudiosDOTai/tunacode/blob/3333c1c0bc3e8d8e963aa37a3d249e4e0fe80163/src/tunacode/core/agents/agent_components/streaming.py#L1-L6))
   - Explain pydantic_ai streaming constraints
   - Document state management during failures
   - Reference this research document

7. **Add KB Entry**
   ```bash
   claude-kb add debug_history \
     --component "streaming" \
     --summary "Streaming retry state corruption bug" \
     --error "AssertionError: stream() should only be called once per node" \
     --solution "Reset node._did_stream=False in exception handler, remove retry loop"
   ```

### Testing

8. **Create Characterization Test**
   - Test: Streaming failure with provider error
   - Assert: Node state is reset properly
   - Assert: Agent continues without crash
   - File: `tests/characterization/agent/test_streaming_failure_recovery.py`

9. **Create Regression Test**
   - Test: Multiple stream attempts on same node
   - Assert: No AssertionError raised
   - Assert: Graceful degradation to non-streaming mode

---

## Architectural Insights

### Design Tension: Retry vs Immutability

**Pydantic_AI Philosophy:** Nodes are immutable request/response pairs

**Tunacode Intent:** Retry transient failures for better UX

**Conflict:** Cannot retry immutable operation on same object

**Resolution Options:**
1. **Accept immutability** - Remove retry, degrade immediately on failure ✓ (chosen)
2. **Request new node** - Ask pydantic_ai for fresh node for retry (not supported)
3. **Hack state** - Manually reset `_did_stream` (fragile, may break in updates)

Current recommendation: Option 1 with Option 3 as cleanup (reset for degradation, not retry)

### State Management Complexity

**Three Layers of State:**
1. **Node state** (`node._did_stream`, `node._result`)
2. **Session state** (`state_manager.session._debug_*`)
3. **Agent loop state** (`response_state`, `tool_buffer`)

**Challenge:** Exception in layer 1 must propagate cleanup to layers 2 and 3

**Current Gap:** Only layer 1 cleanup exists (and it's incomplete)

**Needed:** Coordinated cleanup protocol across all three layers

---

## Summary

This is a **critical bug** that crashes the agent when LLM providers return errors during streaming. The root cause is a retry loop that violates pydantic_ai's single-stream-per-node constraint, leaving the node in a corrupt state (`_did_stream=True`, `_result=None`).

**Three-Part Failure Sequence:**
1. Retry logic calls `node.stream()` twice → AssertionError
2. Exception handler fails to reset `node._did_stream` → state corruption
3. Main loop receives corrupt node → "You must finish streaming before calling run()"

**Simple Fix:** Reset `node._did_stream = False` in exception handler and remove retry loop.

**Status:** Ready for implementation phase - all necessary context documented.
