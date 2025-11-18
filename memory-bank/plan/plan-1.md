# Plan: Implement Pydantic-AI HTTP Transport Retry Layer

**Date:** 2025-11-18
**Status:** Ready for Implementation
**Phase:** Architecture Alignment
**Research Reference:** `memory-bank/research/2025-11-18_13-08-42_streaming-retry-state-corruption.md`

---

## Context

**Problem:** Previous retry logic in `streaming.py` fought pydantic-ai's architecture by attempting to call `node.stream()` multiple times, violating the single-stream-per-node constraint.

**Root Cause:** Retries were happening at the wrong layer - AFTER node creation instead of at the HTTP request layer.

**Solution:** Use pydantic-ai's built-in `AsyncTenacityTransport` to handle retries at the HTTP client level, BEFORE nodes are created.

---

## Phase 1: Cleanup (✅ COMPLETED)

### Changes Made to `streaming.py`

**Removed:**
- Line 38: `for attempt in range(2):` retry loop
- Line 267: Success break statement
- Lines 283-289: Second-attempt conditional and UI message
- Retry counter from logging (`attempt + 1`)

**Updated:**
- Lines 28-33: Docstring now states "degrades gracefully" instead of "performs up to one retry"
- Lines 270-272: Simplified error logging without attempt counter
- Lines 278-281: UI warning message changed to "Streaming failed; falling back to non-streaming mode"

**De-indented:**
- Entire try/except block (lines 39-277) reduced by one indentation level

**Result:**
- Streaming function attempts exactly once per call
- Complies with pydantic_ai's single-stream-per-node constraint
- Degrades gracefully to non-streaming on any failure
- Cleaner, more maintainable code structure
- File reduced from 290 → 278 lines (12 lines removed)

---

## Phase 2: Implement HTTP Layer Retry (NEXT)

### Architecture Pattern

**Correct Layer for Retries:**
```
HTTP Request (with retries)
    ↓ [Retry happens here via AsyncTenacityTransport]
Provider Response
    ↓
Node Creation (only if request succeeded)
    ↓
Streaming (single attempt, no retries)
```

**Key Insight:** If HTTP request fails and retries, node never gets created in corrupt state. Retries happen transparently at transport layer.

### Reference: Pydantic-AI Documentation Pattern

From https://ai.pydantic.dev/retries/:

```python
from httpx import AsyncClient, HTTPStatusError
from tenacity import retry_if_exception_type, stop_after_attempt
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig, wait_retry_after

transport = AsyncTenacityTransport(
    config=RetryConfig(
        retry=retry_if_exception_type(HTTPStatusError),
        wait=wait_retry_after(max_wait=120),
        stop=stop_after_attempt(5),
        reraise=True
    ),
    validate_response=lambda r: r.raise_for_status()
)
client = AsyncClient(transport=transport)
```

**Benefits:**
- Automatically respects HTTP 429 `Retry-After` headers
- Exponential backoff for transient failures
- Configurable max attempts and wait times
- Works for ALL HTTP requests (not just streaming)

---

## Implementation Plan

### File: `src/tunacode/core/agents/agent_components/agent_config.py`

**Location:** Function `get_or_create_agent()` around line 195

**Current Code (line 195-200):**
```python
agent = Agent(
    model=model,
    system_prompt=system_prompt,
    tools=tools_list,
    mcp_servers=mcp_servers,
)
```

**Proposed Changes:**

#### 1. Add Imports (top of file)
```python
from httpx import AsyncClient, HTTPStatusError
from tenacity import retry_if_exception_type, stop_after_attempt
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig, wait_retry_after
```

#### 2. Create HTTP Client with Retry Config (before Agent creation)
```python
# Configure HTTP client with retry logic at transport layer
# This handles retries BEFORE node creation, avoiding pydantic-ai's
# single-stream-per-node constraint violations
transport = AsyncTenacityTransport(
    config=RetryConfig(
        retry=retry_if_exception_type(HTTPStatusError),
        wait=wait_retry_after(
            max_wait=60  # Don't wait more than 60 seconds between retries
        ),
        stop=stop_after_attempt(max_retries),  # Use user-configured max_retries
        reraise=True  # Re-raise final exception after all retries exhausted
    ),
    validate_response=lambda r: r.raise_for_status()
)
http_client = AsyncClient(transport=transport)
```

#### 3. Pass HTTP Client to Agent
```python
agent = Agent(
    model=model,
    system_prompt=system_prompt,
    tools=tools_list,
    mcp_servers=mcp_servers,
    http_client=http_client,  # ADD THIS LINE
)
```

---

## Configuration Integration

### User Config Leverage

**Existing Setting:** `settings.max_retries` (default: 10)

Currently used for:
- Tool execution retry counts
- Now will ALSO control HTTP request retries

**From:** `src/tunacode/configuration/defaults.py:20`
```python
"max_retries": 10,  # Default in user config
```

**Key Description:** `src/tunacode/configuration/key_descriptions.py:84-91`
```python
"settings.max_retries": KeyDescription(
    name="max_retries",
    description="How many times to retry failed API calls",
    example=10,
    help_text="Higher values = more resilient to temporary API issues, "
              "but slower when APIs are down.",
)
```

**Perfect Fit:** This description already covers what we're implementing!

---

## Retry Strategy Details

### What Gets Retried

**HTTP Status Codes:**
- 429 (Rate Limit) - respects `Retry-After` header
- 500 (Internal Server Error)
- 502 (Bad Gateway)
- 503 (Service Unavailable)
- 504 (Gateway Timeout)

All handled by `HTTPStatusError` exception type.

### Wait Strategy

**`wait_retry_after()` behavior:**
1. Checks HTTP response for `Retry-After` header
2. If present (HTTP 429), waits specified time (up to `max_wait`)
3. If absent, falls back to exponential backoff
4. Never exceeds `max_wait` parameter

**Example progression:**
- Attempt 1: Immediate
- Attempt 2: Wait per `Retry-After` or exponential (e.g., 2s)
- Attempt 3: Wait per `Retry-After` or exponential (e.g., 4s)
- etc., up to `max_retries` attempts, never waiting > 60s

---

## Benefits of This Approach

### 1. Architecturally Sound
- Retries happen at correct layer (HTTP transport)
- No violation of pydantic-ai node constraints
- Aligns with pydantic-ai best practices

### 2. Handles More Failure Cases
- **Old approach:** Only retried streaming failures
- **New approach:** Retries ALL HTTP failures (streaming, tool calls, everything)

### 3. Smarter Retry Logic
- Respects rate limit headers
- Exponential backoff prevents server hammering
- Configurable limits prevent infinite loops

### 4. Cleaner Code
- Retry logic centralized in one place
- No scattered try/except retry loops
- Easier to maintain and test

### 5. Better User Experience
- Automatic recovery from transient API issues
- No manual intervention needed for temporary failures
- Transparent to end users

---

## Testing Strategy

### Unit Tests
- Mock `AsyncClient` with transport
- Simulate HTTP 429 responses with `Retry-After` headers
- Verify retry attempts and wait times
- Test max_retries limit enforcement

### Integration Tests
- Real API calls to providers
- Inject temporary failures (if possible via test mode)
- Verify graceful recovery

### Characterization Tests
- Ensure existing behavior preserved
- Verify no regressions in streaming functionality
- Test degradation to non-streaming mode

**Test File Location:** `tests/characterization/agent/test_http_retry_transport.py`

---

## Rollout Plan

### Step 1: Feature Flag (Optional)
Add config option to enable/disable new retry transport:
```python
"settings": {
    "use_http_retry_transport": True,  # Enable new retry layer
    "max_retries": 10
}
```

### Step 2: Implement in Agent Config
Make changes to `agent_config.py` as outlined above.

### Step 3: Add Tests
Create characterization tests for retry behavior.

### Step 4: Monitor
- Watch for retry-related logs
- Track API error rates
- Measure impact on response times

### Step 5: Document
- Update agent architecture docs
- Add retry configuration to user guide
- Update KB entries

---

## Dependencies

### Required Packages

**Check if already installed:**
```bash
pip list | grep pydantic-ai
pip list | grep tenacity
pip list | grep httpx
```

**Installation (if needed):**
```bash
pip install 'pydantic-ai-slim[retries]'
```

This installs:
- `pydantic-ai` core
- `tenacity` retry library
- `httpx` HTTP client

---

## Risk Assessment

### Low Risk
- ✅ No breaking changes to existing API
- ✅ Retry config uses existing `max_retries` setting
- ✅ Graceful degradation if transport fails
- ✅ Well-documented pydantic-ai pattern

### Potential Issues
- ⚠️ Increased latency during retries (expected, acceptable)
- ⚠️ May mask underlying API issues (mitigated by logging)
- ⚠️ Need to ensure client cleanup (httpx AsyncClient needs proper close)

### Mitigation
- Log all retry attempts with context
- Monitor retry rates in production
- Ensure AsyncClient lifecycle management (use context manager or explicit close)

---

## Success Criteria

### Functional
- [ ] HTTP retries work for all provider API calls
- [ ] Retry-After headers respected for 429 responses
- [ ] Max retries limit enforced
- [ ] Graceful degradation on final failure

### Code Quality
- [ ] No retry loops scattered across codebase
- [ ] Centralized retry configuration
- [ ] Clear logging of retry attempts
- [ ] Tests cover retry scenarios

### Performance
- [ ] No regression in happy-path latency
- [ ] Retry delays within acceptable bounds
- [ ] Resource cleanup (no leaked connections)

---

## References

### Research Documents
- `memory-bank/research/2025-11-18_13-08-42_streaming-retry-state-corruption.md`
- `memory-bank/research/2025-11-17_15-06-17_retry-rate-limit-configuration.md`

### Pydantic-AI Documentation
- [HTTP Request Retries](https://ai.pydantic.dev/retries/)
- [pydantic_ai.retries API](https://ai.pydantic.dev/api/retries/)

### Code Locations
- `src/tunacode/core/agents/agent_components/agent_config.py` (lines 195-200)
- `src/tunacode/core/agents/agent_components/streaming.py` (cleaned up, no retry loop)
- `src/tunacode/configuration/defaults.py` (max_retries config)

### Knowledge Base
- `.claude/debug_history/agent_components.streaming.json` (streaming bug entry)

---

## Next Actions

1. ✅ **Verify dependencies:** Check if `pydantic-ai[retries]` installed
2. ⬜ **Implement transport:** Add AsyncTenacityTransport to `agent_config.py`
3. ⬜ **Test locally:** Run characterization tests
4. ⬜ **Commit changes:** Small, focused commit with clear message
5. ⬜ **Update KB:** Document the new retry pattern
6. ⬜ **Monitor:** Watch logs for retry behavior in practice

---

## Notes

**Philosophy:** Work WITH pydantic-ai's architecture, not against it.

**Key Principle:** Retries should happen at the layer that can safely retry - the HTTP transport layer, not the node streaming layer.

**Maintainability:** One centralized retry configuration is easier to understand, test, and modify than scattered retry loops.
