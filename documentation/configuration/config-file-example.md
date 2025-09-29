# TunaCode Configuration File Example

The TunaCode configuration file is located at `~/.config/tunacode.json`. This file stores your API keys, model preferences, and various settings.

## Example Configuration

```json
{
    "default_model": "openrouter:openai/gpt-4.1",
    "env": {
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENROUTER_API_KEY": "sk-or-v1-your-api-key-here"
    },
    "settings": {
        "max_retries": 10,
        "max_iterations": 40,
        "tool_ignore": ,
        "guide_file": "AGENTS.md",
        "fallback_response": true,
        "fallback_verbosity": "normal",
        "context_window_size": 200000,
        "tool_strict_validation": false
    },
    "mcpServers": {}
}
```

## Configuration Options

### Top Level
- `default_model`: The default AI model to use (format: `provider:model-name`)
- `env`: API keys for different providers
- `settings`: Various runtime settings
- `mcpServers`: MCP server configurations (if using Model Context Protocol)

### Settings
- `max_retries`: Maximum number of retries for failed operations (default: 10)
- `max_iterations`: Maximum iterations the agent can use per request (default: 40)
- `tool_ignore`: List of tools to ignore (e.g., `["read_file"]`)
- `guide_file`: Project-specific instructions file (default: `AGENTS.md`)
- `fallback_response`: Enable fallback responses when iterations are exhausted (default: true)
- `fallback_verbosity`: Verbosity of fallback responses (`minimal`, `normal`, `detailed`)
- `context_window_size`: Maximum context window size in tokens (default: 200000)
- `tool_strict_validation`: Whether tools use strict parameter validation (default: false)

## Creating the Config File

You can create the config file in several ways:

1. **Setup Wizard**: Run `tunacode --setup`
2. **CLI Flags**: `tunacode --model "provider:model" --key "your-api-key"`
3. **Manual**: Create the file at `~/.config/tunacode.json` with the structure above

## Changing Settings at Runtime

- Use `/iterations 30` to temporarily change max iterations for the current session
- Use `/model` to switch models during a session
