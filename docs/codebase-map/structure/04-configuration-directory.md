---
title: Configuration Module
path: tunacode/configuration
type: directory
depth: 1
description: Application settings, model registry, and pricing data
seams: [settings, models, pricing, defaults]
---

# Configuration Module (`src/tunacode/configuration`)

## Where
`src/tunacode/configuration/` - Application configuration and settings management.

## What
Manages **all aspects of TunaCode configuration**:
- **User Settings**: `settings.py` - Application preferences and defaults
- **Model Registry**: `models.py` + `models_registry.json` - Available AI models
- **Pricing Data**: `pricing.py` - Cost tracking and token pricing
- **Defaults**: `defaults.py` - Factory default configuration

## Directory Structure
```
configuration/
├── __init__.py              # Package exports
├── settings.py              # User settings management
├── models.py                # Model definitions and metadata
├── models_registry.json     # Model database (provider, capabilities, pricing)
├── pricing.py               # Token pricing and cost calculation
└── defaults.py              # Default configuration values
```

## How
The configuration module implements a **layered configuration system**:

### Configuration Layers
Configuration is loaded in priority order:
1. **Code Defaults**: Hardcoded in `defaults.py`
2. **User Config**: `~/.tunacode/tunacode.json`
3. **Environment Variables**: `.env` file or shell environment
4. **Command-Line Args**: Runtime overrides

### Settings System (`settings.py`)
Manages user preferences:
```python
class Settings:
    # Model Configuration
    model: str

    # Behavior
    timeout: float
    max_retries: int
    auto_confirm: bool

    # UI Preferences
    theme: str

    # Provider-Specific Settings
    providers: {
        "<provider_name>": {
            "base_url": str | None  # Per-provider base URL override
        }
    }
```

**Base URL Resolution** (in `agent_config.py`):
1. Per-provider config: `settings.providers.<provider>.base_url`
2. Registry default: `models_registry.json` → provider `api` field
3. OpenAI escape hatch: `OPENAI_BASE_URL` env var (non-Anthropic only)

**Settings Features**:
- **Schema Validation**: Pydantic models validate settings
- **Migration**: Versioned settings support schema changes
- **Defaults**: Automatic fallback to factory defaults
- **Hot Reload**: Settings can be reloaded without restart

### Model Registry (`models.py` + `models_registry.json`)
Database of available AI models:

**Model Metadata**:
```json
{
  "model_id": {
    "provider": "anthropic",
    "name": "Claude 3 Opus",
    "context_window": 200000,
    "supports_vision": true,
    "supports_tools": true,
    "input_price": 0.015,
    "output_price": 0.075,
    "capabilities": ["tool_use", "vision", "streaming"]
  }
}
```

**Registry Features**:
- **Provider Support**: Anthropic, OpenAI, Google, local models
- **Capability Detection**: Tool use, vision, streaming support
- **Version Tracking**: Model aliases and versioning
- **Lazy Loading**: Models loaded on-demand to reduce startup time

### Pricing System (`pricing.py`)
Tracks token usage and costs:
```python
class ModelPricing:
    input_price_per_1k: float  # Cost per 1K input tokens
    output_price_per_1k: float # Cost per 1K output tokens
    currency: str = "USD"

    def calculate_cost(input_tokens: int, output_tokens: int) -> float:
        """Calculate total cost in currency."""
```

**Pricing Features**:
- **Real-Time Tracking**: Cost updates during streaming
- **Session Totals**: Cumulative cost across all requests
- **Budget Alerts**: Warnings when approaching spending limits
- **Multi-Currency**: Extensible currency support (default USD)

### Defaults System (`defaults.py`)
Factory default configuration:
```python
DEFAULT_SETTINGS = {
    "model": "claude-opus-4-5-20251101",
    "timeout": 120.0,
    "max_retries": 3,
    "theme": "tunacode",
    "auto_confirm": False,
    # ... more defaults
}
```

**Default Strategy**:
- **Sensible Defaults**: Work out-of-the-box for most users
- **Documentation**: Each default includes explanatory comment
- **Override Points**: Clear path to override any default
- **Versioning**: Defaults can evolve with application versions

## Why
**Configuration Centralization**: All settings managed in one place:
- **Maintainability**: Single source of truth for configuration
- **Consistency**: All parts of app use same config values
- **Testability**: Default config enables reproducible tests
- **Documentation**: Settings are self-documenting via Pydantic models

**User Experience**:
- **Zero Config**: Works immediately with sensible defaults
- **Progressive Enhancement**: Advanced users can customize deeply
- **Clear Errors**: Validation errors explain exactly what's wrong
- **Migration**: Settings upgrades preserve user preferences

**Design Principles**:
1. **Explicit Over Implicit**: Config values are visible and obvious
2. **Fail Fast**: Invalid config caught at startup, not runtime
3. **Backward Compatible**: Old config files work with new versions
4. **Documented**: Every setting has clear documentation
5. **Secure**: API keys never logged or displayed

## Integration Points
- **Core Agents**: `tunacode.core` reads model settings for API initialization
- **Token Usage**: `tunacode.core.token_usage` uses pricing data for cost calculation
- **UI**: `tunacode.ui` displays settings and runs setup wizard
- **CLI**: Command-line args override config file values

## Code Quality Notes
- **Type Safety**: Pydantic models enforce type checking
- **Validation**: Complex validation rules for config values
- **Documentation**: Docstrings explain each setting's purpose
- **Testing**: Config validation tested with edge cases
- **Performance**: Lazy loading of model registry for fast startup

## Configuration Files
- **User Config**: `~/.tunacode/tunacode.json`
- **Environment**: `.env` file in project root
- **Session Data**: `~/.tunacode/sessions/<session_id>/`
