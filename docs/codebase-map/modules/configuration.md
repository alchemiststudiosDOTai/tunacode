---
title: Configuration Module
path: src/tunacode/configuration
type: directory
depth: 1
description: User settings, model registry, and pricing management
exports: [load_user_config, ModelRegistry, get_pricing]
seams: [M]
---

# Configuration Module

## Purpose
Manages application configuration including user settings, model registry, pricing information, and default values.

## Key Components

### settings.py
**load_user_config()**
- Loads user configuration from config directory
- Merges with defaults
- Validates configuration structure
- Returns UserConfig dictionary

**Config Locations:**
- `~/.config/tunacode/config.json`
- `.tunacode/config.json` (project-specific)

### models.py
**ModelRegistry Class**
- Loads model definitions from models_registry.json
- Provides model lookup by name
- Validates model configurations
- Caches registry for performance

**Model Registry Format:**
```json
{
  "models": {
    "claude-opus-4-5": {
      "api": "anthropic",
      "max_tokens": 200000,
      "supports_tool_use": true
    }
  }
}
```

### defaults.py
**DEFAULT_USER_CONFIG**
Default configuration values:
- **default_model** - Default LLM to use
- **theme** - UI theme preference
- **yolo_mode** - Authorization bypass
- **max_iterations** - Agent loop limit
- And more...

### Rolling Summary Configuration

These settings control automatic conversation compaction:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enable_rolling_summaries` | bool | `false` | Enable automatic rolling summaries when token threshold exceeded |
| `summary_threshold` | int | `40000` | Token count threshold for triggering summary generation |
| `local_summary_threshold` | int | `6000` | Token threshold when `local_mode: true` (for resource-constrained environments) |

**Consumed by:**
- `core/limits.py` - `get_summary_threshold()` reads these values
- `core/agents/main.py` - `_maybe_generate_summary()` triggers compaction

### pricing.py
**get_pricing()**
- Retrieves pricing information for models
- Calculates token costs
- Supports multiple providers (Anthropic, OpenAI, etc.)
- Tracks session costs

**Pricing Data:**
- Input token costs (per 1M tokens)
- Output token costs (per 1M tokens)
- Cached in pricing.json

## Configuration Schema

**UserConfig Structure:**
```python
{
  "default_model": str,
  "theme": str,
  "yolo_mode": bool,
  "tool_ignore": list[str],
  "max_iterations": int,
  "timeout_seconds": int,
  # ... additional settings
}
```

## Integration Points

- **core/state.py** - Session configuration loading
- **core/agents/** - Model selection and agent creation
- **ui/** - Theme and preference application
- **types/** - UserConfig type definition

## Seams (M)

**Modification Points:**
- Add new configuration options
- Customize default values
- Extend model registry format
- Add new pricing models
