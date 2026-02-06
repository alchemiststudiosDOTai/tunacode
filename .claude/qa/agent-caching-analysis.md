---
title: Agent Caching Architecture - Deep Analysis & Rebuild Plan
type: analysis
status: active
created: 2026-02-06
tags: [caching, agent, prompt-caching, architecture, rebuild]
---

# Agent Caching Architecture: Deep Analysis & Rebuild Plan

## 1. Current Architecture Map

### 1.1 The Agent Loop (message flow)

```
User Input
    |
    v
process_request() [main.py:370]
    |
    v
RequestOrchestrator.__init__() [main.py:119]
    |--- Creates HistoryPreparer
    |--- Creates EmptyResponseHandler
    |--- Reads AgentConfig from user_config
    |
    v
RequestOrchestrator.run() [main.py:148]
    |--- Applies global_request_timeout
    |
    v
RequestOrchestrator._run_impl() [main.py:167]
    |
    |--- ac.get_or_create_agent(model, state_manager)   <-- AGENT CACHING
    |--- history_preparer.prepare(logger)                <-- HISTORY PREP
    |
    v
agent.iter(message, message_history=message_history)     <-- PYDANTIC-AI CALL
    |
    v
async for node in run_handle:                            <-- ITERATION LOOP
    |
    |--- stream_model_request_node()     [streaming.py]
    |--- process_node()                  [orchestrator.py]
    |       |--- emit_tool_returns()
    |       |--- record_thought()
    |       |--- update_usage()          <-- USAGE/COST TRACKING
    |       |--- dispatch_tools()
    |
    v
_persist_run_messages()                                  <-- SAVE TO SESSION
```

### 1.2 Three Distinct "Caching" Layers

The codebase has **three separate caching concerns** that are currently entangled:

#### Layer A: Agent Object Caching (Python-level)
**Where:** `agent_config.py:56-57`, `agent_config.py:345-457`
**What:** Caches the `pydantic_ai.Agent` *Python object* (with its HTTP client, tools, system prompt)
across requests within a session. Avoids re-constructing the agent for every message.

```python
_AGENT_CACHE: dict[ModelName, PydanticAgent] = {}
_AGENT_CACHE_VERSION: dict[ModelName, int] = {}
```

- **Two-tier**: Module-level dict + session-level `state_manager.session.agents`
- **Invalidation**: On abort, timeout, model change, config change
- **Version key**: hash of (max_retries, tool_strict_validation, request_delay, timeout)
- **System prompt**: Baked into agent at creation time, includes AGENTS.md content

#### Layer B: Message History Management (conversation-level)
**Where:** `history_preparer.py`, `resume/sanitize.py`, `resume/prune.py`
**What:** Manages the conversation message list that is passed as `message_history`
to `agent.iter()`. This is the raw conversation context sent to the LLM API.

Operations:
1. **Prune old tool outputs** (`prune.py`) - replaces old tool results with `[Old tool result content cleared]` after 40k tokens of recent content
2. **Cleanup loop** (`sanitize.py:506`) - removes dangling tool calls, empty responses, consecutive requests
3. **System prompt stripping** (`sanitize.py:460`) - strips system-prompt parts (pydantic-ai re-injects them)
4. **Drop trailing requests** (`history_preparer.py:80`) - prevents consecutive user messages

#### Layer C: API-Level Prompt Caching (Anthropic)
**Where:** DOES NOT EXIST
**What should be here:** `cache_control` breakpoints on system prompt, tools, and conversation history.

**Current state:** Zero prompt caching. The `cached_tokens` field in usage tracking exists solely to
*read* what the API reports back, but nothing in the codebase *causes* caching to happen.

---

## 2. Gap Analysis: Current vs. Best Practices

### 2.1 What Anthropic Prompt Caching Provides

| Feature | Capability | Our Status |
|---------|-----------|------------|
| System prompt caching | Cache 4.7KB system prompt + AGENTS.md | **NOT USED** |
| Tool definition caching | Cache 8 tool definitions | **NOT USED** |
| Message history caching | Cache conversation prefix | **NOT USED** |
| Explicit CachePoint markers | Mark cache boundaries in messages | **NOT USED** |
| AnthropicModelSettings | pydantic-ai native support since v0.1.19 | **NOT USED** (we have v1.25.1) |

### 2.2 Cost Impact (estimated per request, Sonnet 4.5)

For a typical multi-turn request with ~50k context tokens:

| Scenario | Cost per request | Savings |
|----------|-----------------|---------|
| No caching (current) | $0.15 | baseline |
| System+tools cached | ~$0.12 | ~20% |
| System+tools+history cached | ~$0.05 | ~67% |
| All layers cached (optimal) | ~$0.03 | ~80% |

### 2.3 Specific Problems Found

**Problem 1: System prompt is rebuilt every agent creation, not cached at API level.**
The system prompt (4.7KB ~1.2k tokens) + AGENTS.md context gets baked into the Agent object.
It IS sent every request. But no `cache_control` marker tells Anthropic to cache it.
For Sonnet 4/4.5 (1024 token minimum), the system prompt alone qualifies for caching.

**Problem 2: Tool definitions are sent uncached every request.**
8 tools with descriptions are ~2-4k tokens. Sent fresh every time. No caching.

**Problem 3: Conversation history grows linearly with no API-level caching.**
As conversation grows, the *entire* history is re-tokenized and charged at full input price.
The prune.py system reclaims tokens by replacing old tool outputs, but doesn't leverage
Anthropic's ability to cache the conversation prefix at 10% cost.

**Problem 4: Agent object caching confuses "don't rebuild Python objects" with "API prompt caching".**
The `_AGENT_CACHE` system caches the Python Agent object to avoid HTTP client reconstruction.
This is a valid optimization but has zero relationship to prompt caching. The naming and
placement makes it appear like caching is handled, when the actual cost-saving caching is absent.

**Problem 5: Usage tracking reads cached_tokens but nothing produces them.**
`usage_tracker.py` correctly reads `cached_tokens` from the API response and factors it into
cost calculation. But since no cache_control markers are set, `cached_tokens` is always 0.
The pricing code handles `cache_read` pricing correctly - it's just never triggered.

**Problem 6: Dual-tier agent cache (module + session) is unnecessary complexity.**
`_AGENT_CACHE` (module dict) and `session.agents` (session dict) store the same Agent object.
The version checking (`_AGENT_CACHE_VERSION`, `session.agent_versions`) adds complexity but
the cache key is just a hash of 4 config values. This should be one cache with one key.

---

## 3. First Principles Decomposition

### 3.1 The Three Orthogonal Concerns

These three concerns must be treated as **independent, non-overlapping responsibilities**:

```
A. Agent Lifecycle    - "When to create/destroy the pydantic-ai Agent object"
B. Context Window     - "What messages to send and how to manage context size"
C. Prompt Caching     - "How to tell the API what to cache for cost/latency savings"
```

They are currently entangled:
- Agent caching (A) lives in `agent_config.py` next to model creation
- Context window (B) is spread across `history_preparer.py`, `sanitize.py`, `prune.py`
- Prompt caching (C) doesn't exist but its tracking code lives in `usage_tracker.py`

### 3.2 First Principles

**Principle 1: Cache boundaries are determined by change frequency.**
- System prompt: changes never during session -> cache with 1h TTL
- Tool definitions: changes never during session -> cache with 1h TTL
- Conversation history prefix: changes every turn -> cache with 5m TTL (auto-refreshes)
- Latest user message: changes every turn -> cache with 5m TTL

**Principle 2: The agent object is an HTTP client wrapper, not a cache strategy.**
The Agent object should be created once and reused. Period. Its lifecycle has nothing
to do with prompt caching. Invalidate only when the HTTP client is broken (abort/timeout).

**Principle 3: Context window management is a content concern, not a caching concern.**
Pruning old tool outputs, removing dangling calls - these are about *what content to send*.
Prompt caching is about *how to send it cheaply*. They compose but don't overlap.

**Principle 4: pydantic-ai already handles the hard parts.**
`AnthropicModelSettings` has `anthropic_cache_instructions`, `anthropic_cache_tool_definitions`,
`anthropic_cache_messages`. `CachePoint` markers can go in message content.
We don't need custom cache_control injection. We need to configure what exists.

---

## 4. Rebuild Plan

### Phase 1: Enable Prompt Caching (highest ROI, smallest change)

**Goal:** Get Anthropic prompt caching working with zero architectural changes.

**File:** `agent_config.py` - modify `get_or_create_agent()`

```python
# When creating the agent for an Anthropic model:
from pydantic_ai.models.anthropic import AnthropicModelSettings

model_settings = AnthropicModelSettings(
    anthropic_cache_instructions=True,      # Cache system prompt (5m TTL)
    anthropic_cache_tool_definitions=True,   # Cache tool definitions (5m TTL)
    anthropic_cache_messages=True,           # Cache last user message (5m TTL)
    max_tokens=max_tokens,                   # Preserve existing behavior
)
```

**Why 5m not 1h:** The 5m TTL auto-refreshes on every hit. For an active coding session,
requests happen more frequently than every 5 minutes. 5m costs 1.25x on write vs 2x for 1h.
Break-even is 2 reads vs 8 reads. 5m is the right default.

**Provider-aware:** Only apply `AnthropicModelSettings` for Anthropic models. OpenAI models
should use regular `ModelSettings`.

**Files changed:** 1 file, ~20 lines. Immediate 60-80% cost reduction on cached content.

### Phase 2: Simplify Agent Object Lifecycle

**Goal:** Replace the dual-tier agent cache with a single, clear lifecycle.

**Current complexity:**
- `_AGENT_CACHE` (module-level dict)
- `_AGENT_CACHE_VERSION` (module-level dict)
- `session.agents` (session-level dict)
- `session.agent_versions` (session-level dict)
- `invalidate_agent_cache()` clears both
- `clear_all_caches()` clears module-level only
- `_compute_agent_version()` hashes 4 config values

**Rebuild to:**
- Single `_AGENT_CACHE: dict[ModelName, tuple[PydanticAgent, int]]` (agent + version)
- One `get_or_create_agent()` that checks version, returns or creates
- One `invalidate_agent()` that clears the entry
- Remove `session.agents` and `session.agent_versions` (eliminate dual-tier)

**Files changed:** `agent_config.py`, `state.py` protocol, `state_structures.py` (remove agents/versions from session), `main.py` (simplify invalidation calls)

### Phase 3: Separate Context Window Management

**Goal:** Make context management a clean pipeline with explicit stages.

**Current pipeline (implicit, spread across files):**
```
messages -> prune_old_tool_outputs() -> run_cleanup_loop() -> drop_trailing_request() -> sanitize_history_for_resume()
```

**Rebuild to explicit pipeline:**
```python
class ContextPipeline:
    """Transforms raw conversation history into API-ready message list."""

    stages = [
        PruneStaleToolOutputs,      # Replace old tool content with placeholder
        RemoveDanglingToolCalls,     # Clean up interrupted tool calls
        RemoveEmptyResponses,        # Drop responses with no content
        DeduplicateRequests,         # Remove consecutive user messages
        StripSystemPrompts,          # Remove system prompts (pydantic-ai adds its own)
    ]

    def prepare(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        """Run all stages in order, return cleaned history."""
```

Each stage is a pure function: `list[Message] -> list[Message]`. Testable in isolation.

**Files changed:** New `context_pipeline.py` replacing `history_preparer.py`. Existing
`resume/` modules become stage implementations. `sanitize.py` splits into focused modules.

### Phase 4: Add CachePoint Strategy for Long Conversations

**Goal:** For conversations beyond ~20 turns, add explicit `CachePoint` markers to
maximize cache hits on the conversation prefix.

**Strategy:** On each new request, if conversation is >20 messages, place a `CachePoint`
at the boundary between "old history" and "recent turns". This uses 1 of the 4 available
cache breakpoints (system prompt and tools use 2, last message uses 1, leaving 1 for
history boundary).

**This is Phase 4 because:** Phase 1's `anthropic_cache_messages=True` already gets
most of the benefit. Explicit CachePoint markers only add value for very long conversations
where the automatic 20-block lookback window isn't sufficient.

---

## 5. File Mapping: What Changes Where

### Phase 1 (Enable Caching)
```
MODIFY  src/tunacode/core/agents/agent_components/agent_config.py
  - Import AnthropicModelSettings
  - Create provider-aware model_settings in get_or_create_agent()
  - Use AnthropicModelSettings for Anthropic, ModelSettings for others
```

### Phase 2 (Simplify Agent Lifecycle)
```
MODIFY  src/tunacode/core/agents/agent_components/agent_config.py
  - Collapse _AGENT_CACHE + _AGENT_CACHE_VERSION into single dict
  - Remove session.agents / session.agent_versions references
  - Simplify get_or_create_agent() to single-tier lookup

MODIFY  src/tunacode/core/types/state.py
  - Remove agents, agent_versions from SessionStateProtocol

MODIFY  src/tunacode/core/types/state_structures.py
  - No changes needed (agents/versions not in structures)

MODIFY  src/tunacode/core/agents/main.py
  - Simplify invalidation calls

MODIFY  src/tunacode/ui/commands/__init__.py
  - Update model-change commands to use simplified invalidation
```

### Phase 3 (Context Pipeline)
```
CREATE  src/tunacode/core/agents/context_pipeline.py
  - Clean pipeline interface

MODIFY  src/tunacode/core/agents/history_preparer.py
  - Delegate to context_pipeline

KEEP    src/tunacode/core/agents/resume/prune.py       (becomes a stage)
KEEP    src/tunacode/core/agents/resume/sanitize.py     (functions become stages)
```

### Phase 4 (CachePoint Strategy)
```
MODIFY  src/tunacode/core/agents/agent_components/agent_config.py
  - Add CachePoint injection logic for long conversations
  - Or modify history_preparer to insert CachePoint markers
```

---

## 6. Validation Criteria

### Phase 1 Success
- [ ] `cached_tokens` in usage output is >0 for Anthropic models after 2nd message
- [ ] Cost per request drops measurably after first message
- [ ] Non-Anthropic models continue working unchanged
- [ ] `uv run pytest` passes

### Phase 2 Success
- [ ] `session.agents` dict removed from SessionStateProtocol
- [ ] Single cache lookup path (no dual-tier)
- [ ] Agent invalidation still works on abort/timeout
- [ ] `uv run pytest` passes

### Phase 3 Success
- [ ] Each cleanup stage is independently testable
- [ ] Pipeline produces identical output to current code for all test cases
- [ ] `uv run pytest` passes

### Phase 4 Success
- [ ] Long conversations (>20 turns) show higher cache hit rates
- [ ] CachePoint count stays within 4-breakpoint limit
- [ ] `uv run pytest` passes
