# TunaCode Configuration Example File

The `tunacode.json.example` file provides a comprehensive template for configuring the TunaCode system. This file demonstrates all available configuration options and their default values.

## File Location

The actual configuration file should be located at:
- **Linux/macOS**: `~/.config/tunacode.json`
- **Windows**: `%APPDATA%\tunacode.json`

## Configuration Structure

```json
{
    "default_model": "openai:gpt-4.1",
    "env": {
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "api-key",
        "OPENROUTER_API_KEY": "",
        "OPENAI_BASE_URL": "https://api.cerebras.ai/v1"
    },
    "settings": {
        "max_retries": 10,
        "max_iterations": 40,
        "tool_ignore": [
            "read_file"
        ],
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
        },
        "enable_tutorial": true,
        "first_installation_date": "2025-09-11T11:50:40.167105",
        "tutorial_declined": true
    },
    "mcpServers": {}
}
```

## Configuration Options

### Default Model
- `default_model`: Default AI model to use (format: `provider:model-name`)
  - Examples: `openai:gpt-4.1`, `anthropic:claude-3-sonnet`, `google:gemini-pro`

### Environment Variables (`env`)
Configure API keys and endpoints for different AI providers:

**Required Keys:**
- `ANTHROPIC_API_KEY`: Anthropic Claude API key (format: `sk-ant-api03-...`)
- `OPENAI_API_KEY`: OpenAI API key (format: `sk-proj-...`)
- `OPENROUTER_API_KEY`: OpenRouter API key

**Optional Keys:**
- `GEMINI_API_KEY`: Google Gemini API key
- `OPENAI_BASE_URL`: Custom OpenAI-compatible endpoint (e.g., Cerebras, LocalAI)

### Settings

**Core Settings:**
- `max_retries`: Maximum retry attempts for failed operations (default: 10)
- `max_iterations`: Maximum agent iterations per request (default: 40)
- `tool_ignore`: List of tools to disable (e.g., `["read_file"]`)
- `guide_file`: Project instruction file (default: `AGENTS.md`)
- `fallback_response`: Enable fallback when iterations exhausted (default: true)
- `fallback_verbosity`: Fallback verbosity level (`minimal`, `normal`, `detailed`)
- `context_window_size`: Maximum context size in tokens (default: 200000)
- `enable_streaming`: Enable streaming responses (default: true)

**Ripgrep Configuration:**
- `use_bundled`: Use bundled ripgrep binary (default: false)
- `timeout`: Ripgrep timeout in seconds (default: 10)
- `max_buffer_size`: Maximum buffer size in bytes (default: 1048576)
- `max_results`: Maximum search results (default: 100)
- `enable_metrics`: Enable ripgrep metrics (default: false)
- `debug`: Enable debug output (default: false)

**Tutorial Settings:**
- `enable_tutorial`: Enable first-time tutorial (default: true)
- `first_installation_date`: Installation timestamp
- `tutorial_declined`: User has declined tutorial (default: false)

### MCP Servers
- `mcpServers`: Model Context Protocol server configurations (empty by default)

## Setup Methods

1. **Copy from Example**:
   ```bash
   cp documentation/configuration/tunacode.json.example ~/.config/tunacode.json
   # Edit the file with your API keys
   ```

2. **Setup Wizard**:
   ```bash
   tunacode --setup
   ```

3. **CLI Configuration**:
   ```bash
   tunacode --model "openai:gpt-4.1" --key "your-api-key"
   ```

## Runtime Configuration Changes

- Change iterations: `/iterations 30`
- Switch models: `/model`
- View current config: `/config`

## Security Notes

- Never commit your actual `tunacode.json` file to version control
- Use environment variables for sensitive keys in production
- Keep API keys secure and rotate them regularly
- The example file contains placeholder values only
