# Research - Model Provider "Not Supported" Issue

**Date:** 2026-01-06
**Owner:** claude
**Phase:** Research

## Goal

Understand why OpenAI-compatible providers like Chutes and MiniMax show "model not supported" errors despite being in the registry.

## Findings

### Root Cause

The issue is a **hardcoded provider allowlist** in `agent_config.py` that only recognizes 6 providers, while the `models_registry.json` contains 50+ providers with full configuration data.

**Hardcoded list** at `src/tunacode/core/agents/agent_components/agent_config.py:253-269`:
```python
PROVIDER_CONFIG = {
    "anthropic": {"api_key_name": "ANTHROPIC_API_KEY", "base_url": None},
    "openai": {"api_key_name": "OPENAI_API_KEY", "base_url": None},
    "openrouter": {...},
    "azure": {...},
    "deepseek": {"api_key_name": "DEEPSEEK_API_KEY", "base_url": None},
    "cerebras": {...},
}
```

**Provider check** at line 290:
```python
elif provider_name in ("openai", "openrouter", "azure", "deepseek", "cerebras"):
```

Any provider NOT in this tuple falls through to line 297-300:
```python
else:
    # Unsupported provider, return string and let pydantic-ai handle it
    return model_string
```

When pydantic-ai receives a raw string like `chutes:deepseek-ai/DeepSeek-V3-0324`, it cannot resolve it and throws the "not supported" error.

### Registry Has Full Provider Data

The `models_registry.json` already contains everything needed:

```
chutes:
  name: Chutes
  env: ['CHUTES_API_KEY']
  api: https://llm.chutes.ai/v1

minimax:
  name: MiniMax
  env: ['MINIMAX_API_KEY']
  api: https://api.minimax.io/anthropic/v1
```

### Relevant Files

| File | Why It Matters |
|------|----------------|
| `src/tunacode/core/agents/agent_components/agent_config.py:241-300` | Contains hardcoded `PROVIDER_CONFIG` and provider check |
| `src/tunacode/configuration/models_registry.json` | Has full provider data (env vars, base URLs) |
| `src/tunacode/configuration/models.py:32-47` | `load_models_registry()` already loads the JSON |
| `src/tunacode/configuration/models.py:76-82` | `get_provider_base_url()` extracts API URL from registry |
| `src/tunacode/configuration/models.py:85-93` | `get_provider_env_var()` extracts env var name from registry |

## Key Patterns / Solutions Found

### Recommended Fix

Replace the hardcoded `PROVIDER_CONFIG` with dynamic lookup from the registry:

1. Import registry functions in `agent_config.py`
2. Use `get_provider_env_var(provider_name)` instead of `config.get("api_key_name")`
3. Use `get_provider_base_url(provider_name)` instead of `config.get("base_url")`
4. Remove the hardcoded tuple check - any provider in registry should work

**Conceptual change**:
```python
# Before (hardcoded)
elif provider_name in ("openai", "openrouter", "azure", "deepseek", "cerebras"):
    config = PROVIDER_CONFIG.get(provider_name, {})
    api_key = env.get(config.get("api_key_name"))
    base_url = config.get("base_url")

# After (dynamic from registry)
elif provider_name != "anthropic":  # All non-anthropic are OpenAI-compatible
    api_key_name = get_provider_env_var(provider_name)
    api_key = env.get(api_key_name) if api_key_name else None
    base_url = get_provider_base_url(provider_name)
```

### Edge Cases to Handle

1. **Anthropic**: Still needs special handling (uses `AnthropicModel`, not `OpenAIChatModel`)
2. **Google/Gemini**: May need special handling if not OpenAI-compatible
3. **Unknown providers**: Fall back gracefully if not in registry

## Knowledge Gaps

- Need to verify which providers in the registry are actually OpenAI-compatible vs needing special SDKs
- MiniMax's base URL ends in `/anthropic/v1` which suggests it might use Anthropic format, not OpenAI

## References

- `src/tunacode/core/agents/agent_components/agent_config.py:241-300` - Provider creation logic
- `src/tunacode/configuration/models.py:76-93` - Registry helper functions that already exist
- `src/tunacode/configuration/models_registry.json` - Full provider metadata
