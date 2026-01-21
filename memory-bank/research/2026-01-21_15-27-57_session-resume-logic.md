# Research - Session Resume Logic Deep Dive

**Date:** 2026-01-21
**Owner:** claude
**Phase:** Research
**Branch:** resume-qa

## Goal

Map the complete session resume logic, focusing on the pydantic-ai system prompt stripping fix documented in the journal entry for 2026-01-21. Understand all message history sanitization functions, their order of execution, and exception handling paths.

## Findings

### Core Implementation Files

| File | Purpose |
|------|---------|
| `src/tunacode/core/agents/main.py` | All sanitization functions, abort exception handling, cleanup orchestration |
| `src/tunacode/core/agents/agent_components/streaming.py` | CancelledError handling in stream loop |
| `src/tunacode/core/agents/agent_components/agent_config.py` | HTTP client config, timeouts, cache invalidation, network logging |
| `src/tunacode/core/state.py` | Session persistence (save/load to JSON) |

### Supporting Files

| File | Purpose |
|------|---------|
| `src/tunacode/types/state.py` | SessionState class definition |
| `src/tunacode/types/pydantic_ai.py` | ModelMessage, ModelResponse, ToolReturn types |
| `tests/integration/core/test_tool_call_lifecycle.py` | Tests for sanitization functions |

---

## Architecture: Message Sanitization Functions

### 1. `_strip_system_prompt_parts()` (main.py:1016-1027)

**Purpose:** Remove `system-prompt` parts from message history.

**Why needed:** pydantic-ai v1.21.0+ automatically injects system prompts via `agent.iter()`. If history contains system prompts from a previous run, the model receives **duplicate system prompts**, causing hangs or unpredictable behavior.

```python
PART_KIND_SYSTEM_PROMPT: str = "system-prompt"

def _strip_system_prompt_parts(parts: list[Any]) -> list[Any]:
    if not parts:
        return parts
    return [p for p in parts if _get_attr_value(p, PART_KIND_ATTR) != PART_KIND_SYSTEM_PROMPT]
```

**Identification method:** Checks `part_kind` attribute equals `"system-prompt"`.

---

### 2. `_remove_dangling_tool_calls()` (main.py:1236-1270)

**Purpose:** Remove tool calls that never received matching tool returns.

**What is a dangling tool call?** When the model requests a tool execution but the operation is aborted before the tool return is added to history. This violates the message invariant: **every tool_call must have a matching tool_return**.

**Detection:** `_find_dangling_tool_call_ids()` (main.py:900-912) computes:
```
dangling = all_tool_call_ids - all_tool_return_ids
```

**When it happens:**
- User aborts (Ctrl+C) mid-tool-execution
- Timeout during tool processing
- Error interrupts tool execution loop

---

### 3. `_remove_empty_responses()` (main.py:977-1010)

**Purpose:** Remove response messages with zero parts.

**What is an empty response?** A message with `kind == "response"` but `parts == []`. Occurs when user aborts after the model starts streaming but before any content parts are generated.

**Why problematic:** Creates invalid sequences like `[Request] [EmptyResponse] [Request]`.

---

### 4. `_remove_consecutive_requests()` (main.py:919-974)

**Purpose:** Remove consecutive request messages, keeping only the last in each run.

**Why consecutive requests are invalid:** API expects alternating pattern:
```
[Request] -> [Response] -> [Request] -> [Response]
```

When user aborts before model responds:
```
[Request] -> [Request]  // INVALID
```

**Resolution:** Keep only the last request in any consecutive run.

---

### 5. `_sanitize_history_for_resume()` (main.py:1029-1093)

**Purpose:** The orchestrating function that creates a clean copy of history for `agent.iter()`.

**Operations:**
1. Strips system-prompt parts using `_strip_system_prompt_parts()`
2. Removes `run_id` attributes (unbinds messages from previous sessions)
3. Drops messages that become empty after stripping

**Key insight:** Returns a NEW list (does not mutate original). Session messages preserved for persistence, sanitized copy sent to API.

---

## Order of Operations

The cleanup runs in an **iterative loop** because each pass can expose new issues:

```
main.py:378-408

for cleanup_iteration in range(max_cleanup_iterations):  # max=10
    any_cleanup = False

    # Step 1: Dangling tool calls
    if _remove_dangling_tool_calls(...): any_cleanup = True

    # Step 2: Empty responses
    if _remove_empty_responses(...): any_cleanup = True

    # Step 3: Consecutive requests
    if _remove_consecutive_requests(...): any_cleanup = True

    if not any_cleanup:
        break  # Transitive closure achieved
```

### Why This Order Matters

1. **Dangling tool calls first** - Most common abort artifact. Removing them may empty messages.
2. **Empty responses second** - After removing dangling calls, some responses may become empty.
3. **Consecutive requests third** - After removing empty responses, `[Req][Empty][Req]` becomes `[Req][Req]`.

### Trailing Request Handling (main.py:413-424)

After the loop, checks for trailing request to prevent `[...Request]` + new user message = consecutive requests:

```python
if session_messages and self.message:
    last_msg = session_messages[-1]
    if last_kind == "request":
        session_messages.pop()  # Drop trailing request
```

---

## Exception Handling Paths

### CancelledError in Streaming (streaming.py:407-422)

```python
except asyncio.CancelledError:
    logger.lifecycle("Stream cancelled")
    # Debug logging of accumulated stream data
    node._did_stream = False  # Allow non-streaming fallback
    raise  # Re-raise to caller
```

**Behavior:** Logs, resets stream flag, re-raises (does NOT swallow).

### UserAbortError/CancelledError in Main (main.py:593-618)

```python
except (UserAbortError, asyncio.CancelledError):
    # 1. Persist partial work
    self._persist_run_messages(agent_run, baseline_message_count)

    # 2. Clean up state
    _remove_dangling_tool_calls(...)
    _remove_empty_responses(...)
    _remove_consecutive_requests(...)

    # 3. Invalidate HTTP client
    invalidate_agent_cache(self.model, self.state_manager)

    raise  # Re-raise
```

**Key behaviors:**
- Persists any accumulated messages from the run
- Runs all three cleanup functions on session messages
- Invalidates agent cache (HTTP client may be in bad state)
- Re-raises exception to caller

---

## HTTP Configuration (agent_config.py)

### Timeouts (line 491)

```python
http_timeout = Timeout(
    10.0,      # connect
    read=60.0,
    write=30.0,
    pool=5.0
)
```

### Network Logging (lines 469-480)

```python
async def log_request(request):
    logger.debug(f"Network OUT: {request.method} {request.url}")

async def log_response(response):
    logger.debug(f"Network IN: {method} {url} -> {status}")
    if status >= 400:
        logger.debug(f"Error Body: {response.text[:500]}")
```

### Agent Cache Invalidation (lines 148-184)

Called after abort to force HTTP client recreation:
```python
def invalidate_agent_cache(model: str, state_manager: StateManager) -> bool:
    if model in _AGENT_CACHE:
        del _AGENT_CACHE[model]
    if model in state_manager.session.agents:
        del state_manager.session.agents[model]
```

---

## Data Flow Summary

```
1. User sends request
   |
2. _run_impl() begins (main.py:348)
   |
3. Session messages retrieved from state_manager.session.messages
   |
4. Cleanup loop runs until stable:
   |  - _find_dangling_tool_call_ids()
   |  - _remove_dangling_tool_calls()
   |  - _remove_empty_responses()
   |  - _remove_consecutive_requests()
   |
5. Trailing request check (drop if present)
   |
6. _sanitize_history_for_resume() creates clean copy:
   |  - Strip system prompts
   |  - Remove run_id bindings
   |  - Drop empty messages
   |
7. Clean history passed to agent.iter() (main.py:500)
   |
8. [SUCCESS] Messages persisted normally
   |
   [ABORT] -> Exception handler (main.py:593):
              - Persist partial work
              - Run all cleanup functions
              - Invalidate agent cache
              - Re-raise exception
```

---

## Key Patterns & Solutions Found

| Pattern | Description |
|---------|-------------|
| **Transitive Closure Cleanup** | Loop until no more changes; one cleanup can expose another |
| **Non-mutating Sanitize** | `_sanitize_history_for_resume()` returns new list, preserves original |
| **Fail-fast on Exception** | Cleanup runs immediately on abort, before re-raising |
| **Dual Storage** | Session messages (mutable, persisted) vs sanitized history (immutable, API copy) |
| **Cache Invalidation** | HTTP client cleared after abort to avoid stale connections |

---

## Current Status

**ISSUE PERSISTING** - Despite the fixes documented above, the session resume hang issue is still occurring. Further investigation needed.

---

## Knowledge Gaps

- How does session persistence interact with compaction? (token pruning may affect message structure)
- What happens if cleanup loop hits max iterations (10)? Is this logged/warned?
- Is there a recovery mechanism if sanitization fails mid-process?

---

## References

### Commits
- `c9b71bb` - fix: strip system prompts from history and add HTTP diagnostics
- `ad53e0b` - fix: resolve session resume hangs after user abort

### Issues
- Issue #269 - Session resume hangs
- pydantic-ai issue #3503 - message_history must start with user message (v1.21.0 breaking change)

### Related Research
- `memory-bank/research/2026-01-21_13-48-19_abort-recovery-modularization.md`
- `memory-bank/research/2026-01-21_13-05-53_stream-hang-abort-root-cause.md`
- `.claude/debug_history/2026-01-21_abort-hang-investigation.md`
- `.claude/delta/2026-01-17-dangling-tool-calls.md`
