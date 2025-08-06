# ESC Key Streaming Cancellation Investigation

## Problem Statement
When pressing ESC during streaming output, the key press doesn't immediately stop the stream. The output continues to render and only shows multiple "Stopped" messages at the end.

## Current Behavior
1. User presses ESC once → Shows "⚠️ Hit ESC again within 3s to stop"
2. User presses ESC second time → Shows "⏹️ Stopped."
3. **BUT** streaming continues rendering until completion
4. Multiple "Stopped" messages appear after streaming finishes

## Attempted Solutions

### 1. Generation-Based Gating (IMPLEMENTED)
**Theory**: Use generation IDs to gate all output - when ESC pressed, invalidate generation so no more writes happen.

**What we implemented**:
- `StateManager` has generation tracking: `new_generation()`, `invalidate_generation()`, `is_current()`
- ESC handler calls `invalidate_generation()` BEFORE `cancel_active()` (keybindings.py:55)
- Added generation checking in main.py streaming loop (lines 226-233)
- REPL streaming callback checks `is_current(gen_id)` before updating panel (repl.py:171)

**Result**: ❌ Still doesn't stop streaming immediately

### 2. Stream Cleanup in Finally Block (IMPLEMENTED)
**Theory**: Ensure UI components are properly cleaned up on cancellation.

**What we implemented**:
- Added streaming panel cleanup in finally block (repl.py:244-255)
- Handles both real panels and test mocks gracefully

**Result**: ✅ Prevents UI corruption, but ❌ doesn't stop streaming

### 3. Cooperative Cancellation in Agent Loop (IMPLEMENTED)
**Theory**: Check generation before processing each node in the agent loop.

**What we implemented**:
- Added generation check at start of node processing loop (main.py:217-220)
- Breaks out of agent iteration if generation invalidated

**Result**: ❌ Still doesn't stop streaming immediately

## Root Cause Analysis

### The Real Problem
The streaming is happening inside `async for event in request_stream:` (main.py:229) which is likely blocking on network I/O. The issue is:

1. **Network-level blocking**: The `request_stream` is probably an HTTP response stream that's reading from a socket
2. **No cooperative yield**: While waiting for the next chunk from the network, the coroutine doesn't yield control
3. **Generation check too late**: We only check `is_current()` AFTER we receive a chunk, not WHILE waiting

### Why Industry Pattern Isn't Working
The standard pattern assumes the stream source is cooperative. But pydantic-ai's stream might be:
- Using a blocking HTTP client under the hood
- Not checking for cancellation while waiting for network data
- Buffering responses that continue to emit even after cancellation

## What We Haven't Tried Yet

### 1. HTTP Client-Level Cancellation
- Need to find where the actual HTTP request is made
- Cancel/close the underlying HTTP connection or request
- This would stop bytes at the network level

### 2. Asyncio Task Cancellation
- The `request_stream` iterator might need to be wrapped in a cancellable task
- Use `asyncio.create_task()` for the streaming loop itself
- Cancel that specific task on ESC

### 3. Stream Wrapper with Timeout
- Wrap the stream iterator with cancellation checking
- Use `asyncio.wait_for()` with small timeout on each iteration
- Check cancellation between timeouts

### 4. Investigate Pydantic-AI Implementation
- Look at how pydantic-ai implements streaming
- Check if it has built-in cancellation support
- May need to monkey-patch or extend their streaming

## Next Steps
1. Find the actual HTTP client code (likely in pydantic-ai)
2. Trace how `node.stream()` is implemented
3. Identify where we can inject cancellation at the transport level
4. Test with aggressive connection closing
