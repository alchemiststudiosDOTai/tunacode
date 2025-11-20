# Research – Global Request Timeout Architecture

**Date:** 2025-11-20T23:45:24Z
**Owner:** context-engineer:research
**Phase:** Research
**Git Commit:** b41dd79b9e590d95aaecd80df9f4fe028b3f0a1e

## Goal

Investigate the current timeout architecture in tunacode to understand:
1. Where timeouts currently exist (tool-level vs. global)
2. The relationship between iteration limits and timeouts
3. How agent execution and model API calls are orchestrated
4. Where a global request timeout should be added (default 90s, configurable via tunacode.json)
5. The configuration system architecture for adding new timeout settings

## Key Finding: Missing Global Request Timeout

**The system has NO global request timeout** at the agent orchestration level. Current timeout mechanisms:
- ✅ **max_iterations**: 40 (iteration limit, NOT a timeout)
- ✅ **Tool-specific timeouts**: bash (30s default, max 300s), grep (10s)
- ❌ **NO global request timeout**: Agent could hang indefinitely waiting for model API response

**What This Means:**
- If model API is slow/unresponsive, no timeout cancels the request
- System relies entirely on model provider's timeout (OpenAI: 120s, Anthropic: 180s)
- User must manually Ctrl+C to interrupt hanging requests

---

## Agent Execution Architecture

### Request Flow

```
User Request
  ↓
execute_repl_request() [/root/tunacode/src/tunacode/cli/repl.py:191]
  ↓
agent.process_request() [/root/tunacode/src/tunacode/core/agents/main.py:583]
  ↓
RequestOrchestrator.__init__() [main.py:297]
  ↓
RequestOrchestrator.run() [main.py:364]
  ↓
async with agent.iter(message, ...) [main.py:381] ⚠️ NO TIMEOUT HERE
  ↓
async for node in agent_run: [main.py:383]
  ├─ Stream tokens [streaming.py:39]
  ├─ Process node [node_processor.py]
  ├─ Execute tools (WITH tool-specific timeouts)
  ├─ Check iteration limit [main.py:456]
  └─ Continue loop...
```

### Where Global Timeout Should Be Enforced

**Option 1 (Recommended): RequestOrchestrator.run() wrapper**
- **File**: `/root/tunacode/src/tunacode/core/agents/main.py:364`
- **Method**: Wrap entire `async with agent.iter(...)` block with `asyncio.wait_for()`
- **Advantage**: Catches all model API hangs and iteration processing time
- **Implementation**:
  ```python
  async def run(self) -> AgentRunWithState:
      global_timeout = _coerce_global_request_timeout(self.state_manager)
      try:
          return await asyncio.wait_for(
              self._run_impl(),  # Existing logic moved here
              timeout=global_timeout
          )
      except asyncio.TimeoutError:
          raise GlobalRequestTimeoutError(global_timeout)
  ```

**Option 2: process_request() wrapper**
- **File**: `/root/tunacode/src/tunacode/core/agents/main.py:583`
- **Method**: Wrap orchestrator.run() call
- **Advantage**: Higher level, applies to all request types
- **Disadvantage**: Less granular than Option 1

**Option 3: execute_repl_request() wrapper**
- **File**: `/root/tunacode/src/tunacode/cli/repl.py:191`
- **Method**: Wrap agent.process_request() call
- **Disadvantage**: Too high-level, misses non-REPL requests

---

## Existing Timeout Mechanisms

### 1. Tool-Specific Timeouts

| Tool | File | Default | Max | Configurable |
|------|------|---------|-----|--------------|
| **bash** | `/root/tunacode/src/tunacode/tools/bash.py:129` | 30s | 300s | Per-invocation |
| **ripgrep** | `/root/tunacode/src/tunacode/configuration/defaults.py:31` | 10s | - | Via config |
| **grep first match** | `/root/tunacode/src/tunacode/tools/grep_components/search_result.py:35` | 3.0s | - | Hardcoded |

**Bash Timeout Implementation** (`bash.py:193`):
```python
await asyncio.wait_for(process.communicate(), timeout=timeout)
```

**Ripgrep Timeout** (`ripgrep.py:204`):
```python
subprocess.run(..., timeout=timeout)
```

### 2. Iteration Limit (NOT a Timeout)

- **File**: `/root/tunacode/src/tunacode/core/agents/main.py:59`
- **Default**: 15 (configured via `settings.max_iterations`, typically 40)
- **Check Location**: `/root/tunacode/src/tunacode/core/agents/main.py:136-149`
- **Behavior**: Pauses agent with `awaiting_user_guidance` flag after max iterations
- **Key Point**: This is a **counter**, not a timeout. Execution continues until iteration completes.

**Relationship Between Iteration Limit and Timeouts:**
- **Independent mechanisms**: Iteration limit counts loops; timeouts measure wall-clock time
- **Both can trigger**: A request could timeout AND hit iteration limit
- **Timing**: Iteration limit checked AFTER each iteration completes, not during

### 3. Request Delay (Pre-Request Pause)

- **File**: `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py:69-82`
- **Default**: 0.0 seconds
- **Range**: 0.0 to 60.0 seconds
- **Purpose**: Pause BEFORE each API call (rate limiting)
- **Implementation**: `asyncio.sleep()` with countdown spinner
- **Key Point**: This is a **delay**, not a timeout

---

## Configuration System Architecture

### Current Configuration Structure

**File**: `/root/tunacode/src/tunacode/configuration/defaults.py:11-39`

```python
DEFAULT_USER_CONFIG: UserConfig = {
    "default_model": "openrouter:openai/gpt-4.1",
    "env": {
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
        # ...
    },
    "settings": {
        "max_retries": 10,
        "max_iterations": 40,
        "request_delay": 0.0,
        # ⚠️ MISSING: "global_request_timeout": 90.0
        "tool_ignore": [],
        "ripgrep": {
            "timeout": 10,
            "max_buffer_size": 1048576,
            # ...
        },
    },
    "mcpServers": {},
}
```

### Configuration Loading Flow

1. **Load from file**: `/root/tunacode/utils/user_configuration.py:33-58`
   - File location: `~/.config/tunacode.json`
   - Uses SHA1 fingerprint for caching
   - Returns `None` if file not found, raises `ConfigurationError` on JSON parse failure

2. **Setup and validation**: `/root/tunacode/core/setup/config_setup.py:45-176`
   - Merges with defaults
   - Validates API keys
   - Falls back to alternative models if key missing

3. **Store in StateManager**: `state_manager.session.user_config`

4. **Access pattern**:
   ```python
   settings = state_manager.session.user_config.get("settings", {})
   timeout = float(settings.get("global_request_timeout", 90.0))
   ```

### Example: How request_delay Works (Pattern to Follow)

**Default Definition** (`defaults.py:22`):
```python
"request_delay": 0.0,
```

**Validation Function** (`agent_config.py:85-94`):
```python
def _coerce_request_delay(state_manager: StateManager) -> float:
    """Return validated request_delay from config."""
    settings = state_manager.session.user_config.get("settings", {})
    request_delay_raw = settings.get("request_delay", 0.0)
    request_delay = float(request_delay_raw)

    if request_delay < 0.0 or request_delay > 60.0:
        raise ValueError(f"request_delay must be between 0.0 and 60.0 seconds, got {request_delay}")

    return request_delay
```

**Usage** (`agent_config.py:285`):
```python
request_delay = _coerce_request_delay(state_manager)
```

**Documentation** (`key_descriptions.py:102-108`):
```python
"settings.request_delay": KeyDescription(
    name="request_delay",
    description="Delay in seconds before each API request",
    example=0.0,
    help_text="Adds a fixed pause before every LLM API call to avoid rate-limit bursts.",
    category="Behavior Settings",
),
```

---

## Implementation Plan for global_request_timeout

### Step 1: Add to Default Configuration

**File**: `/root/tunacode/src/tunacode/configuration/defaults.py:22`

**Add after `request_delay`**:
```python
"settings": {
    "max_retries": 10,
    "max_iterations": 40,
    "request_delay": 0.0,
    "global_request_timeout": 90.0,  # NEW: 90 seconds default
    # ...
}
```

### Step 2: Add Key Description

**File**: `/root/tunacode/src/tunacode/configuration/key_descriptions.py:~108`

**Add after `"settings.request_delay"`**:
```python
"settings.global_request_timeout": KeyDescription(
    name="global_request_timeout",
    description="Global timeout for all API requests in seconds",
    example=90.0,
    help_text="Maximum time to wait for any agent request to complete. "
              "Prevents indefinite hangs when model API is unresponsive. "
              "Set to 0.0 to disable (not recommended). "
              "Typical values: 30-300 seconds.",
    category="Behavior Settings",
),
```

### Step 3: Add Validation Function

**File**: `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py:~95`

**Add after `_coerce_request_delay()`**:
```python
def _coerce_global_request_timeout(state_manager: StateManager) -> float:
    """Return validated global_request_timeout from config."""
    settings = state_manager.session.user_config.get("settings", {})
    timeout_raw = settings.get("global_request_timeout", 90.0)
    timeout = float(timeout_raw)

    if timeout < 0.0:
        raise ValueError(f"global_request_timeout must be >= 0.0 seconds, got {timeout}")

    # 0.0 means no timeout (disable)
    return timeout if timeout > 0.0 else None
```

### Step 4: Implement Timeout Wrapper

**File**: `/root/tunacode/src/tunacode/core/agents/main.py:364`

**Refactor `run()` method**:
```python
async def run(self) -> AgentRunWithState:
    """Execute agent request with global timeout."""
    global_timeout = _coerce_global_request_timeout(self.state_manager)

    try:
        if global_timeout is not None:
            return await asyncio.wait_for(
                self._run_impl(),
                timeout=global_timeout
            )
        else:
            return await self._run_impl()
    except asyncio.TimeoutError:
        raise GlobalRequestTimeoutError(
            f"Request timed out after {global_timeout} seconds. "
            f"Increase 'global_request_timeout' in tunacode.json or wait for model response."
        )

async def _run_impl(self) -> AgentRunWithState:
    """Original run logic (moved from run())."""
    # ... existing logic from lines 366-490 ...
```

### Step 5: Add Exception Class

**File**: `/root/tunacode/src/tunacode/exceptions.py:~228`

**Add new exception**:
```python
class GlobalRequestTimeoutError(Exception):
    """Raised when a request exceeds the global timeout."""
    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Request exceeded global timeout of {timeout_seconds} seconds. "
            f"The model API may be slow or unresponsive."
        )
```

### Step 6: Update Agent Version Hash (Cache Invalidation)

**File**: `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py:97-108`

**Add to hash computation**:
```python
def _compute_agent_version(
    settings: Dict[str, Any], request_delay: float, mcp_servers: dict
) -> int:
    """Compute a hash representing agent-defining configuration."""
    return hash(
        (
            str(settings.get("max_retries", 3)),
            str(settings.get("tool_strict_validation", False)),
            str(request_delay),
            str(settings.get("global_request_timeout", 90.0)),  # NEW
            str(mcp_servers),
        )
    )
```

### Step 7: Update Documentation

**Files to update**:
- `/root/tunacode/documentation/configuration/tunacode-json-example.md:~25`
- `/root/tunacode/documentation/configuration/config-file-example.md:~18`
- `/root/tunacode/README.md:~106`

**Example JSON addition**:
```json
"settings": {
    "max_retries": 10,
    "max_iterations": 40,
    "request_delay": 0.0,
    "global_request_timeout": 90.0,
    "tool_ignore": []
}
```

---

## Key Files Reference

### Timeout-Related Files

| Component | File | Key Lines |
|-----------|------|-----------|
| **Request Orchestrator** | `/root/tunacode/src/tunacode/core/agents/main.py` | 364-490 |
| **Agent Config** | `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py` | 283-392 |
| **Bash Tool Timeout** | `/root/tunacode/src/tunacode/tools/bash.py` | 129, 193 |
| **Grep Tool Timeout** | `/root/tunacode/src/tunacode/tools/grep.py` | 290, 304 |
| **Iteration Manager** | `/root/tunacode/src/tunacode/core/agents/main.py` | 132-149 |
| **Request Delay** | `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py` | 69-94 |

### Configuration-Related Files

| Component | File | Key Lines |
|-----------|------|-----------|
| **Default Config** | `/root/tunacode/src/tunacode/configuration/defaults.py` | 11-39 |
| **Key Descriptions** | `/root/tunacode/src/tunacode/configuration/key_descriptions.py` | 26-240 |
| **Config Loading** | `/root/tunacode/src/tunacode/utils/user_configuration.py` | 33-58, 61-81 |
| **Config Setup** | `/root/tunacode/src/tunacode/core/setup/config_setup.py` | 45-176 |
| **Exceptions** | `/root/tunacode/src/tunacode/exceptions.py` | 223-228 |

### Execution Flow Files

| Component | File | Key Lines |
|-----------|------|-----------|
| **REPL Entry** | `/root/tunacode/src/tunacode/cli/repl.py` | 191 |
| **Process Request** | `/root/tunacode/src/tunacode/core/agents/main.py` | 583-599 |
| **Agent Iteration** | `/root/tunacode/src/tunacode/core/agents/main.py` | 381-458 |
| **Node Processing** | `/root/tunacode/src/tunacode/core/agents/agent_components/node_processor.py` | 23-561 |
| **Tool Execution** | `/root/tunacode/src/tunacode/core/agents/agent_components/tool_executor.py` | - |
| **Streaming** | `/root/tunacode/src/tunacode/core/agents/agent_components/streaming.py` | 39 |

---

## Additional Search Commands

```bash
# Find all timeout-related code
grep -ri "timeout" src/tunacode/ --include="*.py" | grep -v test | grep -v "__pycache__"

# Find all asyncio.wait_for calls (existing timeout patterns)
grep -r "wait_for" src/tunacode/ --include="*.py"

# Find agent iteration logic
grep -r "agent.iter" src/tunacode/ --include="*.py"

# Find config loading
grep -r "user_config.get" src/tunacode/ --include="*.py"
```

---

## Findings Summary

### Relevant Files and Why They Matter

1. **`/root/tunacode/src/tunacode/core/agents/main.py`**
   - **Reason**: Contains RequestOrchestrator.run() where global timeout wrapper should be added
   - **Key**: Lines 364-490 (run method), 381 (agent.iter call point)

2. **`/root/tunacode/src/tunacode/configuration/defaults.py`**
   - **Reason**: Where `global_request_timeout: 90.0` should be added to settings
   - **Key**: Lines 11-39 (DEFAULT_USER_CONFIG)

3. **`/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py`**
   - **Reason**: Pattern for validation function (`_coerce_request_delay` at 85-94)
   - **Key**: Lines 85-94 (validation pattern), 97-108 (version hash)

4. **`/root/tunacode/src/tunacode/configuration/key_descriptions.py`**
   - **Reason**: Documentation for new config field
   - **Key**: Line ~108 (after request_delay description)

5. **`/root/tunacode/src/tunacode/exceptions.py`**
   - **Reason**: Add GlobalRequestTimeoutError exception
   - **Key**: Line ~228 (after PatternSearchTimeoutError)

6. **`/root/tunacode/src/tunacode/tools/bash.py`**
   - **Reason**: Example of tool-specific timeout using asyncio.wait_for
   - **Key**: Line 193 (timeout implementation pattern)

7. **`/root/tunacode/src/tunacode/utils/user_configuration.py`**
   - **Reason**: Config loading logic (no changes needed, but good reference)
   - **Key**: Lines 33-58 (load_config function)

---

## Key Patterns and Solutions Found

### Pattern 1: Timeout Wrapper with asyncio.wait_for

**Example from bash.py:193**:
```python
stdout, stderr = await asyncio.wait_for(
    process.communicate(),
    timeout=timeout
)
```

**Apply to global request**:
```python
return await asyncio.wait_for(
    self._run_impl(),
    timeout=global_timeout
)
```

### Pattern 2: Config Validation Function

**Example from agent_config.py:85-94**:
```python
def _coerce_request_delay(state_manager: StateManager) -> float:
    settings = state_manager.session.user_config.get("settings", {})
    value_raw = settings.get("request_delay", 0.0)
    value = float(value_raw)

    if value < 0.0 or value > 60.0:
        raise ValueError(f"...")

    return value
```

**Apply to global_request_timeout**:
- Default: 90.0 seconds
- Range: 0.0 (disabled) to infinity
- Type: float
- Validation: Ensure >= 0.0, return None if 0.0 (disabled)

### Pattern 3: Exception Handling

**Example from exceptions.py:223-228**:
```python
class PatternSearchTimeoutError(Exception):
    def __init__(self, pattern: str, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        # ...
```

**Apply to global timeout**:
- Exception name: `GlobalRequestTimeoutError`
- Parameters: `timeout_seconds: float`
- Message: Helpful guidance about increasing timeout or model slowness

---

## Knowledge Gaps

### Questions to Resolve in Implementation Phase

1. **Error message UX**: Should timeout error show:
   - Current model being used?
   - Number of iterations completed before timeout?
   - Recommendation for timeout value adjustment?

2. **Timeout interaction with streaming**:
   - Should timeout apply to entire streaming session or per-chunk?
   - Current assumption: Entire request (first token to completion)

3. **Timeout value recommendations**:
   - Default 90s is conservative
   - Should there be different defaults for different model providers?
   - Should docs mention typical values per provider?

4. **Backward compatibility**:
   - Config field is new, defaults to 90.0
   - Existing configs without field will use default
   - No migration needed

5. **Testing strategy**:
   - How to test timeout without waiting 90 seconds?
   - Mock model API with intentional delay?
   - Test with timeout=1.0 and slow operation?

---

## References

### Related Plans
- `/root/tunacode/memory-bank/plan/2025-11-20_rate-limit-signaling-plan.md` - Rate limit error handling
- `/root/tunacode/memory-bank/plan/2025-11-19_10-00-00_main_agent_error_handling_hardening.md` - Error handling enhancement

### Related Research
- `/root/tunacode/memory-bank/research/2025-11-17_15-06-17_retry-rate-limit-configuration.md` - Retry config analysis
- `/root/tunacode/memory-bank/research/2025-09-07_21-13-37_agent_loop_architecture.md` - Agent loop architecture

### Documentation
- `/root/tunacode/documentation/configuration/tunacode-json-example.md` - Config schema example
- `/root/tunacode/documentation/configuration/config-file-example.md` - User-facing config guide
- `/root/tunacode/documentation/agent/main-agent-architecture.md` - Agent architecture docs

### Test Reference
- `/root/tunacode/tests/test_agent_config_request_delay.py` - Example of timeout config testing pattern
