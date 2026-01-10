# Research – agent_config.py File Map

**Date:** 2026-01-10
**Owner:** context-engineer
**Phase:** Research

## Goal

Comprehensive mapping of `src/tunacode/core/agents/agent_components/agent_config.py` - the central agent factory and configuration module.

---

## File Overview

**Path:** `src/tunacode/core/agents/agent_components/agent_config.py`
**Lines:** 442
**Purpose:** Agent configuration, caching, and creation utilities

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        agent_config.py                              │
├─────────────────────────────────────────────────────────────────────┤
│  MODULE CACHES (Lines 41-46)                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ _PROMPT_CACHE   │  │ _TUNACODE_CACHE │  │ _AGENT_CACHE        │  │
│  │ dict[str,       │  │ dict[str,       │  │ dict[ModelName,     │  │
│  │  (str, float)]  │  │  (str, float)]  │  │  PydanticAgent]     │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘  │
│           │                    │                      │             │
│           ▼                    ▼                      ▼             │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              get_or_create_agent() [Lines 340-441]          │    │
│  │                     MAIN ENTRY POINT                        │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌─────────────────────┐
│ load_system   │     │ load_tunacode   │     │ _create_model_with  │
│ _prompt()     │     │ _context()      │     │ _retry()            │
│ [205-236]     │     │ [238-265]       │     │ [268-337]           │
└───────────────┘     └─────────────────┘     └─────────────────────┘
```

---

## Module-Level Caches

| Cache | Type | Purpose | Invalidation |
|-------|------|---------|--------------|
| `_PROMPT_CACHE` | `dict[str, tuple[str, float]]` | Caches system prompts by path | File mtime change |
| `_TUNACODE_CACHE` | `dict[str, tuple[str, float]]` | Caches AGENTS.md content | File mtime change |
| `_AGENT_CACHE` | `dict[ModelName, PydanticAgent]` | Caches agent instances | Config version change |
| `_AGENT_CACHE_VERSION` | `dict[ModelName, int]` | Tracks config hash per model | Manual on config change |

---

## Function Map

### Public API

| Function | Lines | Signature | Purpose |
|----------|-------|-----------|---------|
| `get_or_create_agent` | 340-441 | `(model: ModelName, state_manager: StateManager) -> PydanticAgent` | **Main factory** - creates/retrieves cached agent |
| `clear_all_caches` | 167-172 | `() -> None` | Clears all module caches (for testing) |

### Internal Functions (Used by Other Modules)

| Function | Lines | Signature | Used By |
|----------|-------|-----------|---------|
| `_coerce_global_request_timeout` | 97-109 | `(StateManager) -> float \| None` | `main.py` |
| `_coerce_request_delay` | 85-94 | `(StateManager) -> float` | `research_agent.py` |
| `_build_request_hooks` | 151-164 | `(float, StateManager) -> dict[...]` | `research_agent.py` |
| `_create_model_with_retry` | 268-337 | `(str, AsyncClient, StateManager) -> Model` | `research_agent.py` |

### Private Functions (Internal Only)

| Function | Lines | Purpose |
|----------|-------|---------|
| `_format_request_delay_message` | 51-53 | Formats countdown message string |
| `_publish_delay_message` | 56-66 | Updates UI spinner (best-effort, non-blocking) |
| `_sleep_with_countdown` | 69-82 | Sleep with visual countdown steps |
| `_coerce_optional_str` | 112-123 | Validates/normalizes optional string values |
| `_resolve_base_url_override` | 126-136 | Resolves API base URL (env > settings) |
| `_compute_agent_version` | 139-148 | Hashes config for cache invalidation |
| `get_agent_tool` | 175-179 | Lazy import to avoid circular deps |
| `_read_prompt_from_path` | 182-202 | Reads prompts with mtime caching |
| `load_system_prompt` | 205-235 | Loads/composes system prompt from sections |
| `load_tunacode_context` | 238-265 | Loads AGENTS.md if present |

---

## Provider Configuration (Lines 287-303)

```python
PROVIDER_CONFIG = {
    "anthropic": {"api_key_name": "ANTHROPIC_API_KEY", "base_url": None},
    "openai":    {"api_key_name": "OPENAI_API_KEY", "base_url": None},
    "openrouter": {
        "api_key_name": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
    },
    "azure": {
        "api_key_name": "AZURE_OPENAI_API_KEY",
        "base_url": env.get("AZURE_OPENAI_ENDPOINT"),
    },
    "deepseek": {"api_key_name": "DEEPSEEK_API_KEY", "base_url": None},
    "cerebras": {
        "api_key_name": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
    },
}
```

### Model String Parsing (Lines 306-317)

```
Format: "provider:model_name" or just "model_name"

Auto-detection rules:
  - Starts with "claude" → anthropic
  - Starts with "gpt", "o1", "o3" → openai
  - Otherwise → passed to pydantic-ai for auto-detect
```

---

## Registered Tools (Lines 385-408)

| Tool | Source Module | Purpose |
|------|---------------|---------|
| `bash` | `tunacode.tools.bash` | Shell command execution |
| `glob` | `tunacode.tools.glob` | File pattern matching |
| `grep` | `tunacode.tools.grep` | Content search |
| `list_dir` | `tunacode.tools.list_dir` | Directory listing |
| `read_file` | `tunacode.tools.read_file` | File reading |
| `update_file` | `tunacode.tools.update_file` | File editing |
| `web_fetch` | `tunacode.tools.web_fetch` | HTTP fetching |
| `write_file` | `tunacode.tools.write_file` | File writing |
| `research_codebase` | `delegation_tools.py` | Multi-agent delegation |
| `todowrite` | `tunacode.tools.todo` | Task tracking (write) |
| `todoread` | `tunacode.tools.todo` | Task tracking (read) |
| `todoclear` | `tunacode.tools.todo` | Task tracking (clear) |

---

## Call Flow: get_or_create_agent()

```
get_or_create_agent(model, state_manager)
    │
    ├─► _coerce_request_delay(state_manager)           # Validate delay 0-60s
    ├─► _compute_agent_version(settings, request_delay) # Hash config
    │
    ├─► CHECK session cache (state_manager.session.agents)
    │       └─► Return if version matches
    │
    ├─► CHECK module cache (_AGENT_CACHE)
    │       └─► Return if version matches
    │
    └─► CREATE NEW AGENT:
            ├─► load_system_prompt(base_path, model)    # Compose prompt
            │       └─► SectionLoader → compose_prompt → resolve_prompt
            │
            ├─► load_tunacode_context()                 # Append AGENTS.md
            │
            ├─► Create tool list (12 tools)
            │
            ├─► AsyncTenacityTransport(...)             # Retry transport
            ├─► _build_request_hooks(...)               # Request delay hooks
            ├─► AsyncClient(transport, event_hooks)     # HTTP client
            │
            ├─► _create_model_with_retry(...)           # Provider-specific model
            │
            └─► Agent(model, system_prompt, tools)      # Create agent
                    │
                    └─► Cache in both _AGENT_CACHE and session
```

---

## Dependency Graph

### Imports FROM agent_config.py

```
agent_config.py
    │
    ├── delegation_tools.py
    │       └── create_research_codebase_tool
    │
    ├── prompting/
    │       ├── MAIN_TEMPLATE
    │       ├── TEMPLATE_OVERRIDES
    │       ├── SectionLoader
    │       ├── SystemPromptSection
    │       ├── compose_prompt
    │       └── resolve_prompt
    │
    ├── state.py
    │       └── StateManager
    │
    └── tools/
            ├── bash.py       → bash
            ├── glob.py       → glob
            ├── grep.py       → grep
            ├── list_dir.py   → list_dir
            ├── read_file.py  → read_file
            ├── todo.py       → create_todo*_tool
            ├── update_file.py → update_file
            ├── web_fetch.py  → web_fetch
            └── write_file.py → write_file
```

### Imports TO agent_config.py

```
Consumers:
    │
    ├── agent_components/__init__.py
    │       └── exports: get_or_create_agent
    │
    ├── main.py
    │       └── uses: _coerce_global_request_timeout, get_or_create_agent
    │
    └── research_agent.py
            └── uses: _build_request_hooks, _coerce_request_delay,
                      _create_model_with_retry
```

---

## Key Patterns

### 1. Two-Level Caching
- **Session cache**: `state_manager.session.agents` - per-conversation
- **Module cache**: `_AGENT_CACHE` - cross-conversation persistence
- Both use version hashing for invalidation

### 2. Config Version Hashing (Line 139-148)
```python
hash((max_retries, tool_strict_validation, request_delay, global_request_timeout))
```
Cache invalidates when any of these settings change.

### 3. Request Delay with Visual Feedback
- Configurable delay (0-60s) before each API request
- Countdown displayed via spinner UI
- Implemented via httpx event hooks

### 4. Transport-Level Retry
Uses `AsyncTenacityTransport` for retries BEFORE pydantic-ai node creation, avoiding stream constraint issues.

---

## Configuration Values

| Setting | Source | Default | Range |
|---------|--------|---------|-------|
| `request_delay` | `settings.request_delay` | 0.0 | 0.0-60.0s |
| `global_request_timeout` | `settings.global_request_timeout` | 90.0 | >= 0.0 (0 = disabled) |
| `max_retries` | `settings.max_retries` | 3 | - |
| `tool_strict_validation` | `settings.tool_strict_validation` | False | bool |
| `base_url` | env or settings | None | string |

---

## References

- `src/tunacode/core/agents/agent_components/agent_config.py` - This file
- `src/tunacode/core/agents/main.py` - Main agent runner
- `src/tunacode/core/agents/research_agent.py` - Sub-agent implementation
- `src/tunacode/core/prompting/` - Prompt composition system
- `src/tunacode/core/state.py` - State management
