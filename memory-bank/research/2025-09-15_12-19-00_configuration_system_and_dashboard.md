# Research – TunaCode Configuration System and Startup Dashboard

**Date:** 2025-09-15
**Owner:** context-engineer
**Phase:** Research

## Goal
Research the tunacode configuration system and startup dashboard to understand configuration loading and how to create a startup dashboard. This should tell me what configs I have for each tool whether it is default or my own etc.

- Additional Search:
  - `grep -ri "dashboard" .claude/`
  - `grep -ri "startup" .claude/`
  - `grep -ri "config" .claude/`

## Findings

### Configuration System Architecture

The TunaCode configuration system is a comprehensive multi-layered approach that handles user preferences, API keys, model settings, and MCP server configurations through JSON-based configuration files.

#### **Configuration File Structure**
- **Location**: `~/.config/tunacode.json` (Linux/macOS) or `%APPDATA%\tunacode.json` (Windows)
- **Format**: JSON with fingerprint-based caching for performance
- **Key files**:
  - `src/tunacode/configuration/defaults.py:11-38` → Default configuration structure
  - `src/tunacode/utils/user_configuration.py:33-58` → Configuration loading and saving
  - `src/tunacode/configuration/settings.py:14-25` → Path management

#### **Configuration Loading Process** (`src/tunacode/utils/user_configuration.py:33-58`)
- Uses SHA-1 fingerprinting for fast-path caching
- Automatic directory creation with secure permissions (0o700)
- JSON validation with descriptive error handling
- Smart merging of user config with defaults

#### **Default Configuration Structure** (`src/tunacode/configuration/defaults.py:11-38`)
```json
{
    "default_model": "openrouter:openai/gpt-4.1",
    "env": {
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENROUTER_API_KEY": ""
    },
    "settings": {
        "max_retries": 10,
        "max_iterations": 40,
        "tool_ignore": ["read_file"],
        "guide_file": "AGENTS.md",
        "fallback_response": true,
        "fallback_verbosity": "normal",
        "context_window_size": 200000,
        "enable_streaming": true,
        "ripgrep": {
            "use_bundled": false,
            "timeout": 10,
            "max_buffer_size": 1048576,
            "max_results": 100,
            "enable_metrics": false,
            "debug": false
        }
    },
    "mcpServers": {}
}
```

### Tool-Specific Configurations

#### **Ripgrep Tool Configuration**
- Located in `settings.ripgrep` section
- Options: bundled binary usage, timeout, buffer size, result limits, metrics, debug mode
- Default timeout: 10 seconds, max results: 100

#### **Tool Configuration Management**
- `tool_ignore` list specifies tools to disable
- `tool_strict_validation` controls parameter validation strictness
- Individual tools can have their own configuration sections

#### **MCP Server Configuration** (`src/tunacode/services/mcp.py:61-108`)
- Supports Model Context Protocol servers
- Cached configuration with hash-based invalidation
- Extensible architecture for external tools

### Startup and Setup System

#### **Setup Coordinator** (`src/tunacode/core/setup/coordinator.py`)
- Manages all setup steps in sequence
- Configuration setup → Environment setup → Template setup → Git safety → Agent setup
- Each step can be forced or run conditionally

#### **Interactive Setup Wizard** (`src/tunacode/core/setup/config_wizard.py:25-57`)
- 4-step guided setup process:
  1. Provider selection (OpenRouter, OpenAI, Anthropic, Google)
  2. API key setup with provider-specific guidance
  3. Model selection with smart recommendations
  4. Optional settings (tutorial preferences)

#### **Environment Variable Integration** (`src/tunacode/core/setup/environment_setup.py:29-49`)
- Automatically exports API keys from config to process environment
- Validates environment variable values
- Provides feedback on successful exports

### UI Components and Dashboard

#### **Terminal-Based UI Architecture**
- Built on **prompt_toolkit** and **Rich** libraries
- No web-based dashboard components exist
- Terminal-native interface works everywhere

#### **Interactive Model Selector** (`src/tunacode/ui/model_selector.py`)
- Real-time search and filtering by provider
- Model details display (cost, limits, capabilities)
- Keyboard navigation support
- Provider grouping and comparison

#### **Configuration Interfaces**
- **Model Management**: `/model` command with interactive selection
- **Setup Wizard**: Step-by-step guided configuration
- **Tutorial System**: Progressive onboarding experience
- **Console UI**: Unified display API with Rich styling

#### **Panel System** (`src/tunacode/ui/panels.py`)
- **StreamingAgentPanel**: Real-time content with animated indicators
- **Help panels**: Command documentation
- **Tool confirmation panels**: File operation previews
- **Message history**: Session conversation display

### Configuration Validation and Error Handling

#### **Smart Validation** (`src/tunacode/core/setup/config_setup.py:194-230`)
- Validates API keys exist for selected models
- Provides fallback model selection when keys missing
- Comprehensive error messages with actionable guidance

#### **Fallback Model Logic** (`src/tunacode/core/setup/config_setup.py:177-192`)
- Preference order: OpenAI → Anthropic → Google → OpenRouter
- Graceful handling of missing configurations
- Automatic model selection based on available API keys

#### **Error Handling** (`src/tunacode/exceptions.py:18-33`)
- ConfigurationError class with suggested fixes and help URLs
- Enhanced error messages with actionable guidance
- Graceful degradation for missing configurations

## Key Patterns / Solutions Found

- **Fingerprint-based caching**: SHA-1 hashing for performance optimization
- **Smart merging**: Ensures backward compatibility with new settings
- **Interactive wizard**: User-friendly setup for new users
- **CLI override support**: Configuration can be overridden via command-line arguments
- **Environment variable integration**: Automatic API key management
- **Terminal-native UI**: No GUI dependencies, works everywhere
- **Progressive disclosure**: Information shown as needed
- **Comprehensive validation**: Robust error handling throughout

## Knowledge Gaps

- No web-based dashboard or graphical interface exists
- No centralized configuration visualization tool
- No real-time configuration monitoring dashboard
- No startup health check dashboard
- Limited documentation on creating custom configuration interfaces

## References

### Core Configuration Files
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9f80f42/src/tunacode/configuration/defaults.py
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9f80f42/src/tunacode/utils/user_configuration.py
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9f80f42/src/tunacode/configuration/settings.py

### Setup and Wizard Files
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9f80f42/src/tunacode/core/setup/config_wizard.py
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9f80f42/src/tunacode/core/setup/coordinator.py
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9f80f42/src/tunacode/core/setup/environment_setup.py

### UI Components
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9f80f42/src/tunacode/ui/model_selector.py
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9f80f42/src/tunacode/ui/panels.py
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9f80f42/src/tunacode/ui/console.py

### Documentation
- `documentation/configuration/config-file-example.md`
- `documentation/ui/ui-architecture.md`
- `memory-bank/research/2025-09-12_14-54-43_model_configuration_crash_analysis.md`
