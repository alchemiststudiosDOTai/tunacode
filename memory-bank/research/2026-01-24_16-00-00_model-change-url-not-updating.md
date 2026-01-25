# Research – Model Change URL Not Updating

**Date:** 2026-01-24
**Owner:** Claude
**Phase:** Research

## Goal

Investigate why changing models via `/model` command doesn't update the base_url - the model name changes but requests still go to the old provider's URL.

## Findings

### Root Cause

When model is changed via `/model`, the **agent cache is NOT invalidated**. The cached agent (created with the OLD provider's base_url) continues to be used.

### Relevant Files

| File | Lines | Why It Matters |
|------|-------|----------------|
| `src/tunacode/ui/commands/__init__.py` | 182-250 | `/model` command implementation - **missing cache invalidation** |
| `src/tunacode/core/agents/agent_components/agent_config.py` | 105-114 | `_compute_agent_version()` - **doesn't include provider settings in hash** |
| `src/tunacode/core/agents/agent_components/agent_config.py` | 138-162 | `invalidate_agent_cache()` - exists but not called on model change |
| `src/tunacode/core/agents/agent_components/agent_config.py` | 349-399 | `get_or_create_agent()` - uses version hash to check cache validity |
| `src/tunacode/core/agents/agent_components/agent_config.py` | 282-346 | `_create_model_with_http_client()` - reads base_url only when creating NEW agent |

### The Gap - Three Missing Pieces

**1. Version Hash Incomplete** (`agent_config.py:105-114`)
```python
def _compute_agent_version(settings: dict[str, Any], request_delay: float) -> int:
    return hash((
        str(settings.get("max_retries", 3)),
        str(settings.get("tool_strict_validation", False)),
        str(request_delay),
        str(settings.get("global_request_timeout", 90.0)),
    ))
    # MISSING: settings.get("providers") not included!
```

**2. Direct Model Switch Missing Invalidation** (`commands/__init__.py:206-211`)
```python
# After updating current_model and saving config:
# MISSING: invalidate_agent_cache() call
```

**3. Picker Flow Missing Invalidation** (`commands/__init__.py:220-237`)
```python
def on_model_selected(full_model: str | None) -> None:
    # Updates session state, saves config
    # MISSING: invalidate_agent_cache() call
```

### Data Flow

```
User: /model anthropic:claude-sonnet
  ↓
ModelCommand.execute() [commands/__init__.py:187]
  ↓
session.current_model = "anthropic:claude-sonnet"  ✓ Updated
session.user_config["default_model"] = "..."       ✓ Updated
save_config()                                      ✓ Saved to disk
  ↓
Next agent request → get_or_create_agent("anthropic:claude-sonnet")
  ↓
Cache miss (different model string) BUT...
  ↓
NEW agent created with CORRECT anthropic base_url  ← Actually works for different provider!
```

**Wait - Different Model = Different Cache Key!**

Re-analyzing: The cache key IS the model string. So switching from `openai:gpt-4` to `anthropic:claude-sonnet` SHOULD create a new agent.

### Refined Analysis

The issue must be when switching to a model **on the SAME provider but with different base_url**, OR when changing settings that affect the URL resolution:

**Scenario 1: Same Provider, Different Config**
```
1. Start with openai:gpt-4, base_url = "https://api.openai.com/v1"
2. User edits config to change openai provider's base_url
3. Switch to openai:gpt-4o
4. Cache hit! Returns old agent with old base_url
```

**Scenario 2: OPENAI_BASE_URL Override**
```
1. Start with openai:gpt-4, no OPENAI_BASE_URL set
2. User sets OPENAI_BASE_URL env var in config
3. Next request uses same model → cache hit → old agent without override
```

### Key Insight: Cache Validity Doesn't Check Provider Settings

The `_compute_agent_version()` hash determines cache validity but **doesn't include**:
- Provider base_url settings
- OPENAI_BASE_URL env var
- Any provider-specific config

So when these change, the cached agent is still considered "valid" even though it has stale configuration.

## Key Patterns / Solutions Found

**Pattern: Cache Invalidation Strategy**

Currently exists in two places:
- `agent_config.py:332` - Called on timeout
- `agent_config.py:598` - Called on user abort

Missing from:
- Model change command
- Provider settings change

**Fix Options:**

1. **Include provider config in version hash** (automatic detection)
   ```python
   def _compute_agent_version(settings, request_delay):
       return hash((
           str(settings.get("max_retries", 3)),
           ...
           str(settings.get("providers", {})),  # ADD THIS
       ))
   ```

2. **Explicit invalidation on model change** (immediate effect)
   ```python
   # In ModelCommand.execute() after updating config:
   invalidate_agent_cache(full_model, app.state_manager)
   ```

3. **Clear ALL agents on model change** (safest but heaviest)
   ```python
   clear_all_caches()
   ```

## Knowledge Gaps

- Need to confirm: Does switching between providers (e.g., openai → anthropic) actually work correctly?
- Is the issue specifically with OPENAI_BASE_URL override not being picked up?
- Does the user have custom provider settings that should override defaults?

## References

- `src/tunacode/ui/commands/__init__.py:182-250` - ModelCommand
- `src/tunacode/core/agents/agent_components/agent_config.py:105-162` - Version hash and cache invalidation
- `src/tunacode/core/agents/main.py:348` - Where get_or_create_agent is called
