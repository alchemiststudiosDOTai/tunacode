# Research – Retry and Rate Limiting Configuration

**Date:** 2025-11-17
**Owner:** Agent
**Phase:** Research
**Branch:** master
**Commit:** 875941c08598c83f0b955cbea485ea945c075049

## Goal

Map out the complete retry and rate-limiting configuration system in TunaCode to understand how time between requests is controlled, what configuration options exist, and where they are implemented.

## Research Query

User wants to understand:
1. How retry/rate-limiting currently works
2. Whether time-between-requests configuration exists
3. Where to add simple configuration for delays between requests

## Key Findings

### Critical Discovery: NO General Rate Limiting Exists

**TunaCode implements NO rate-limiting or inter-request delays for general API calls.** The codebase has three types of delays:

1. **JSON Parsing Retry Delays** - Exponential backoff when JSON parsing fails
2. **Tool Execution Retries** - Framework-level retry count (no delays)
3. **Grep Search Deadline** - Timeout to prevent overly broad searches

**Implication:** API calls to LLM providers have no built-in delays between requests. All rate limiting happens at the API provider level, not in TunaCode.

---

## Detailed Findings by Component

### 1. JSON Parsing Retry Mechanism

**Primary Implementation:** [src/tunacode/utils/retry.py](src/tunacode/utils/retry.py)

#### Configuration Constants (Hardcoded)

[src/tunacode/constants.py:204-207](src/tunacode/constants.py#L204-L207):
```python
JSON_PARSE_MAX_RETRIES = 10        # Maximum retry attempts
JSON_PARSE_BASE_DELAY = 0.1        # Initial delay in seconds
JSON_PARSE_MAX_DELAY = 5.0         # Maximum delay cap
```

**Status:** Not user-configurable, hardcoded in constants.

#### Exponential Backoff Algorithm

[src/tunacode/utils/retry.py:50-58](src/tunacode/utils/retry.py#L50-L58):
```python
delay = min(base_delay * (2**attempt), max_delay)
await asyncio.sleep(delay)
```

**Delay Progression:**
- Attempt 0: 0.1s
- Attempt 1: 0.2s
- Attempt 2: 0.4s
- Attempt 3: 0.8s
- Attempt 4: 1.6s
- Attempt 5: 3.2s
- Attempt 6+: 5.0s (capped at max_delay)

#### Where Used

1. **Agent Utilities** - [src/tunacode/core/agents/utils.py:219-224](src/tunacode/core/agents/utils.py#L219-L224)
   - Fallback JSON parsing for tool responses

2. **Command Parser** - [src/tunacode/cli/repl_components/command_parser.py:40-44](src/tunacode/cli/repl_components/command_parser.py#L40-L44)
   - Parsing slash command arguments

---

### 2. Tool Execution Retry Configuration

**Configuration Entry Point:** [src/tunacode/core/agents/agent_components/agent_config.py:159](src/tunacode/core/agents/agent_components/agent_config.py#L159)

```python
max_retries = state_manager.session.user_config.get("settings", {}).get("max_retries", 3)
```

**Default:** 3 (fallback), but user config defaults to 10

#### User Configuration

[src/tunacode/configuration/defaults.py:20](src/tunacode/configuration/defaults.py#L20):
```python
"max_retries": 10,  # Default in user config
```

[src/tunacode/configuration/key_descriptions.py:84-91](src/tunacode/configuration/key_descriptions.py#L84-L91):
```python
"settings.max_retries": KeyDescription(
    name="max_retries",
    description="How many times to retry failed API calls",
    example=10,
    help_text="Higher values = more resilient to temporary API issues, "
              "but slower when APIs are down.",
)
```

#### Tool Registration

[src/tunacode/core/agents/agent_components/agent_config.py:199-207](src/tunacode/core/agents/agent_components/agent_config.py#L199-L207):
```python
Tool(bash, max_retries=max_retries, strict=tool_strict_validation),
Tool(glob, max_retries=max_retries, strict=tool_strict_validation),
Tool(grep, max_retries=max_retries, strict=tool_strict_validation),
Tool(list_dir, max_retries=max_retries, strict=tool_strict_validation),
Tool(read_file, max_retries=max_retries, strict=tool_strict_validation),
Tool(run_command, max_retries=max_retries, strict=tool_strict_validation),
Tool(todo_tool._execute, max_retries=max_retries, strict=tool_strict_validation),
Tool(update_file, max_retries=max_retries, strict=tool_strict_validation),
Tool(write_file, max_retries=max_retries, strict=tool_strict_validation),
```

**Important:** `max_retries` is a **count**, not a delay mechanism. It tells pydantic_ai how many times to retry a tool invocation, but does NOT introduce delays between retries.

---

### 3. ModelRetry Exception-Based Guidance

**Usage Pattern:** Tools raise `ModelRetry` to guide the LLM to adjust parameters.

[src/tunacode/tools/base.py:56-61](src/tunacode/tools/base.py#L56-L61):
```python
except ModelRetry as e:
    # Log as warning and re-raise for pydantic-ai
    if self.ui:
        await self.ui.warning(str(e))
    self.logger.warning(f"ModelRetry: {e}")
    raise  # Re-raise for pydantic_ai to handle
```

**Example from Bash Tool** - [src/tunacode/tools/bash.py:150-158](src/tunacode/tools/bash.py#L150-L158):
```python
if timeout and (timeout < 1 or timeout > 300):
    raise ModelRetry(
        "Timeout must be between 1 and 300 seconds. "
        "Use shorter timeouts for quick commands, longer for builds/tests."
    )
```

**Mechanism:** W
hen raised, pydantic_ai sends the exception message to the LLM, which adjusts and retries (up to `max_retries` times).

---

### 4. Grep Search Deadline (Only Non-Retry Delay)

[src/tunacode/tools/grep_components/search_result.py:35](src/tunacode/tools/grep_components/search_result.py#L35):
```python
first_match_deadline: float = 3.0  # Timeout for finding first match
```

[src/tunacode/tools/grep.py:404-412](src/tunacode/tools/grep.py#L404-L412):
```python
async def check_deadline():
    await asyncio.sleep(config.first_match_deadline)  # 3 second sleep
    if not first_match_event.is_set():
        for task in search_tasks:
            if not task.done():
                task.cancel()
        raise TooBroadPatternError(pattern, config.first_match_deadline)
```

**Purpose:** Prevents overly broad search patterns from running indefinitely. Not a retry mechanism—it's a timeout.

**Status:** Hardcoded at 3.0 seconds, not user-configurable.

---

### 5. API Client Configuration

**Agent Instantiation:** [src/tunacode/core/agents/agent_components/agent_config.py:213-217](src/tunacode/core/agents/agent_components/agent_config.py#L213-L217)

```python
agent = Agent(
    model=model,
    system_prompt=system_prompt,
    tools=tools_list,
    mcp_servers=mcp_servers,
)
```

**Key Finding:** No timeout, rate-limit, or delay parameters passed to `Agent()` constructor.

#### Streaming Configuration

[src/tunacode/src/tunacode/core/agents/agent_components/streaming.py:266-288](src/tunacode/src/tunacode/core/agents/agent_components/streaming.py#L266-L288):
- Simple retry: 2 attempts maximum (1 retry)
- No exponential backoff
- Fallback to non-streaming on repeated failures

#### API Keys and Endpoints

**Environment Variables:**
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `GEMINI_API_KEY`
- `OPENAI_BASE_URL` (for custom endpoints like LM Studio, Ollama, Cerebras)

**Configuration:** [src/tunacode/configuration/key_descriptions.py:37-82](src/tunacode/configuration/key_descriptions.py#L37-L82)

**Validation:** [src/tunacode/utils/api_key_validation.py:28-93](src/tunacode/utils/api_key_validation.py#L28-L93)

---

## Configuration Summary Table

| Configuration | Location | Default | User-Configurable | Type |
|--------------|----------|---------|-------------------|------|
| `JSON_PARSE_MAX_RETRIES` | constants.py:205 | 10 | ❌ No | Retry count |
| `JSON_PARSE_BASE_DELAY` | constants.py:206 | 0.1s | ❌ No | Initial delay |
| `JSON_PARSE_MAX_DELAY` | constants.py:207 | 5.0s | ❌ No | Max delay |
| `max_retries` (tools) | user config | 10 | ✅ Yes | Retry count |
| `first_match_deadline` | grep search | 3.0s | ❌ No | Timeout |
| Bash tool timeout | tool parameter | 30s | ✅ Yes (1-300s) | Timeout |
| Ripgrep timeout | user config | 10s | ✅ Yes | Timeout |
| **API rate limiting** | N/A | N/A | ❌ Does not exist | N/A |

---

## Relevant Files by Category

### Core Retry Implementation
- [src/tunacode/utils/retry.py](src/tunacode/utils/retry.py) - Exponential backoff decorator
- [src/tunacode/constants.py](src/tunacode/constants.py) - Retry constants (lines 204-207)

### Agent Configuration
- [src/tunacode/core/agents/agent_components/agent_config.py](src/tunacode/core/agents/agent_components/agent_config.py) - Agent and tool initialization
- [src/tunacode/core/agents/utils.py](src/tunacode/core/agents/utils.py) - JSON parsing with retry
- [src/tunacode/core/agents/agent_components/streaming.py](src/tunacode/core/agents/agent_components/streaming.py) - Streaming retry logic

### User Configuration
- [src/tunacode/configuration/defaults.py](src/tunacode/configuration/defaults.py) - Default user config
- [src/tunacode/configuration/key_descriptions.py](src/tunacode/configuration/key_descriptions.py) - Config documentation

### Tool Implementations
- [src/tunacode/tools/base.py](src/tunacode/tools/base.py) - ModelRetry handling
- [src/tunacode/tools/bash.py](src/tunacode/tools/bash.py) - Timeout validation
- [src/tunacode/tools/grep.py](src/tunacode/tools/grep.py) - Search deadline
- [src/tunacode/tools/grep_components/search_result.py](src/tunacode/tools/grep_components/search_result.py) - Search config

### API and Validation
- [src/tunacode/utils/api_key_validation.py](src/tunacode/utils/api_key_validation.py) - API key mapping
- [src/tunacode/services/mcp.py](src/tunacode/services/mcp.py) - MCP server management

### Documentation
- [documentation/configuration/tunacode.json.example](documentation/configuration/tunacode.json.example) - Config examples
- [documentation/agent/tunacode-tool-system.md](documentation/agent/tunacode-tool-system.md) - Tool system docs
- [.claude/patterns/json_retry_implementation.md](.claude/patterns/json_retry_implementation.md) - Retry pattern

---

## Knowledge Gaps

### Missing Configuration for Request Delays

**What DOES NOT exist:**
1. ❌ Configuration for time between general API requests
2. ❌ Rate limiting for API calls to LLM providers
3. ❌ Throttling or cooldown periods between requests
4. ❌ Request queue with delay management

**Where to add this:**

If implementing time-between-requests configuration, the logical locations would be:

1. **User Configuration** - Add to [src/tunacode/configuration/defaults.py](src/tunacode/configuration/defaults.py):
   ```python
   "settings": {
       "max_retries": 10,
       "request_delay": 0.0,  # NEW: Delay between requests in seconds
   }
   ```

2. **Agent Execution** - Modify [src/tunacode/core/agents/agent_components/streaming.py](src/tunacode/core/agents/agent_components/streaming.py) or agent_config.py to inject delays before API calls

3. **Tool Wrapper** - Could intercept tool calls in [src/tunacode/tools/base.py](src/tunacode/tools/base.py) to add delays

---

## Data Flow: Current Retry Journey

```
User Query
    ↓
Agent runs with tools (max_retries from config)
    ↓
Tool call invoked → Tool execution
    ↓
Tool returns success OR raises ModelRetry
    ↓
If ModelRetry:
  - pydantic_ai increments retry count
  - Sends exception message to LLM
  - LLM adjusts parameters
  - Tool called again (up to max_retries times)
  - NO DELAYS between retries (immediate)
    ↓
If JSON parsing error in response:
  - retry_json_parse_async() called
  - Exponential backoff: 0.1s, 0.2s, 0.4s... up to 5.0s
  - Max 10 attempts
  - If all fail: ToolBatchingJSONError raised
    ↓
Result returned to user
```

**Critical Gap:** NO delays exist between normal API requests or tool retries (except JSON parsing).

---

## Search Commands for Additional Context

```bash
# Find all sleep/delay calls
grep -ri "sleep\|delay" src/tunacode/

# Find timeout configurations
grep -ri "timeout" src/tunacode/configuration/

# Find retry implementations
grep -ri "retry" src/tunacode/core/agents/
```

---

## References

### Code Files
- [src/tunacode/utils/retry.py](src/tunacode/utils/retry.py)
- [src/tunacode/constants.py](src/tunacode/constants.py)
- [src/tunacode/core/agents/agent_components/agent_config.py](src/tunacode/core/agents/agent_components/agent_config.py)
- [src/tunacode/configuration/defaults.py](src/tunacode/configuration/defaults.py)

### Documentation
- [documentation/configuration/tunacode.json.example](documentation/configuration/tunacode.json.example)
- [documentation/agent/tunacode-tool-system.md](documentation/agent/tunacode-tool-system.md)

### Patterns
- [.claude/patterns/json_retry_implementation.md](.claude/patterns/json_retry_implementation.md)
