# ESC Key Streaming Cancellation Analysis
_Started: 2025-08-06 16:15:00_
_Agent: code-synthesis-analyzer_

## Research Phase

### Phase 1: File Location Research
[1] Key files in streaming architecture identified:
   - /root/tunacode/src/tunacode/ui/panels.py - StreamingAgentPanel using Rich.Live
   - /root/tunacode/src/tunacode/ui/keybindings.py - ESC handler with prompt_toolkit
   - /root/tunacode/src/tunacode/cli/repl.py - process_request with streaming callback
   - /root/tunacode/src/tunacode/core/agents/main.py - agent streaming logic
   - /root/tunacode/core/state.py - StateManager with generation tracking

[2] Previous fix attempts documented in ESC_KEY_INVESTIGATION.md:
   - Generation-based gating (implemented but not working)
   - Stream cleanup in finally block (helps but doesn't stop stream)
   - Cooperative cancellation in agent loop (not effective)
   - Latest: Exception-based context manager exit (commit 070965e)

### Phase 2: Implementation Logic Research
[3] Streaming architecture flow from HTTP to terminal:
   1. User input → REPL process_request (repl.py:99)
   2. Generation ID created for tracking (repl.py:161)
   3. StreamingAgentPanel created with Rich.Live (repl.py:163-164)
   4. Agent.process_request called with streaming_callback (repl.py:175)
   5. Agent iterates through nodes (main.py:213)
   6. For model request nodes, node.stream() creates HTTP stream (main.py:233)
   7. Stream events are TextPartDelta tokens (main.py:240-242)
   8. Callback updates StreamingAgentPanel via Rich.Live (repl.py:173)
   9. Rich.Live refreshes terminal 4x/second (panels.py:124)

[4] Cancellation check points:
   - ESC handler: invalidates generation + cancels task (keybindings.py:55-57)
   - Before node processing: checks is_current(gen_id) (main.py:218-220)
   - Inside streaming loop: checks is_current(gen_id) (main.py:236)
   - Latest fix: raises StreamCancelled exception (main.py:238)

[5] Why generation gating doesn't work immediately:
   - The async for loop blocks on network I/O waiting for next chunk
   - Generation check only happens AFTER receiving each chunk
   - No cooperative yield while waiting for HTTP response data
   - pydantic-ai's stream likely uses blocking HTTP client underneath

### Phase 3: Synthesis
[6] Root cause: Network-level blocking in HTTP response stream
   - `async for event in request_stream` blocks on socket read
   - No cancellation check DURING the wait for next chunk
   - Generation invalidation doesn't interrupt the blocking I/O
   - Exception approach (StreamCancelled) only works between chunks

[7] Why current approaches fail:
   - Generation gating: Only checked after receiving data, not during wait
   - Task cancellation: HTTP stream not properly cancelled at transport level
   - Exception exit: Still waits for next chunk before checking generation
   - Rich.Live continues updating with buffered data even after stop()

[8] Missing pieces:
   - No access to underlying HTTP client/connection to force close
   - pydantic-ai's stream implementation details unknown
   - No timeout/cancellation token passed to stream iterator
   - Stream may be buffering responses that continue to emit

[9] pydantic-ai streaming details discovered:
   - Uses provider-specific AsyncStream (e.g., openai.AsyncStream)
   - Stream is wrapped in PeekableAsyncStream utility
   - Context manager (`async with response`) handles HTTP connection
   - No explicit cancellation mechanism exposed in the API

[10] Critical finding: The streaming loop architecture:
   ```
   async with node.stream() as request_stream:  # Opens HTTP connection
       async for event in request_stream:        # Blocks on socket read
           if not is_current(gen_id):           # Check AFTER receiving data
               raise StreamCancelled()          # Exception to exit context
   ```

   The problem: `async for` blocks waiting for next chunk from server
   No interruption possible until data arrives

## Analysis Summary

[11] Why ESC key doesn't stop streaming immediately:
   1. **Network I/O Blocking**: The `async for event in request_stream` blocks on socket read operations
   2. **Late Cancellation Check**: Generation validation only happens after receiving each chunk
   3. **No Preemptive Interruption**: No way to interrupt the wait for the next chunk
   4. **HTTP Connection Persistence**: The underlying HTTP connection remains open until naturally closed
   5. **Rich.Live Buffer**: Terminal continues updating with any buffered content

[12] What would be needed for immediate cancellation:
   - Access to the underlying HTTP client to force-close the connection
   - Timeout wrapper around the stream iterator with periodic checks
   - Cancellation token passed to the HTTP library
   - Or: Wrap the entire streaming task in asyncio.Task and cancel it
