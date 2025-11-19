# TunaCode + Chutes.ai Setup Guide

This guide provides step-by-step instructions for configuring TunaCode to work with chutes.ai's OpenAI-compatible API endpoint.

## Overview

Chutes.ai provides an OpenAI-compatible API that allows you to use various AI models through their platform. This guide shows how to configure TunaCode to use chutes.ai as your default AI provider.

## Quick Setup

### 1. Locate Your Configuration File

The TunaCode configuration file is located at:
```
~/.config/tunacode.json
```

If it doesn't exist, TunaCode will create one during setup.

### 2. Get Your Chutes.ai Credentials

Before starting, you'll need:
- **API Key**: Your chutes.ai API key (format: `cpk_...`)
- **Model**: The model you want to use (e.g., `MiniMaxAI/MiniMax-M2`)

### 3. Configuration Template

Replace the contents of your `tunacode.json` with this template:

```json
{
    "default_model": "openai:MiniMaxAI/MiniMax-M2",
    "env": {
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "YOUR_CHUTES_API_KEY_HERE",
        "OPENAI_BASE_URL": "https://llm.chutes.ai/v1",
        "OPENROUTER_API_KEY": ""
    },
    "settings": {
        "max_retries": 10,
        "max_iterations": 40,
        "tool_ignore": [],
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
        "enable_tutorial": false
    },
    "mcpServers": {}
}
```

## Detailed Configuration Steps

### Step 1: Backup Your Existing Configuration

```bash
cp ~/.config/tunacode.json ~/.config/tunacode.json.backup
```

### Step 2: Add Chutes.ai Configuration

Edit your `tunacode.json` file and update these key fields:

#### 2.1 Set the Default Model
```json
"default_model": "openai:MiniMaxAI/MiniMax-M2"
```

**Important**: Use the `openai:` prefix even though you're connecting to chutes.ai. This tells TunaCode to use the OpenAI-compatible API client.

#### 2.2 Configure the API Key
```json
"OPENAI_API_KEY": "cpk_250ce57ba42f4dd4b0e18f9b5e443451.1335c9e9008f5b15b96b2882a192a118.zhQbtTRGYbfQtlNWauLkmDtJCnYxvs2t"
```

Replace the example key with your actual chutes.ai API key.

#### 2.3 Set the Base URL
```json
"OPENAI_BASE_URL": "https://llm.chutes.ai/v1"
```

**Critical**: The URL must end with `/v1`. TunaCode will automatically append the appropriate endpoint paths (`/chat/completions`, etc.).

## Configuration Patterns

### Pattern 1: Multiple Provider Support

Keep support for multiple AI providers by configuring all relevant keys:

```json
"env": {
    "ANTHROPIC_API_KEY": "your-anthropic-key",
    "GEMINI_API_KEY": "your-gemini-key",
    "OPENAI_API_KEY": "cpk_your-chutes-key",
    "OPENAI_BASE_URL": "https://llm.chutes.ai/v1",
    "OPENROUTER_API_KEY": "sk-or-your-openrouter-key"
},
"default_model": "openai:MiniMaxAI/MiniMax-M2"
```

### Pattern 2: Model Switching

You can switch between models by changing the `default_model`:

```json
// Use chutes.ai with MiniMax
"default_model": "openai:MiniMaxAI/MiniMax-M2"

// Use chutes.ai with other models
"default_model": "openai:gpt-4o"
"default_model": "openai:claude-3-haiku"
```

### Pattern 3: Runtime Model Switching

Use TunaCode commands to switch models temporarily:

```bash
# Switch to a different model for the current session
/model "openai:gpt-4o"

# Check current model
/model
```

## Available Models

Chutes.ai supports various models. Common options include:

- `MiniMaxAI/MiniMax-M2` (recommended for general use)
- `openai/gpt-4o`
- `openai/gpt-4o-mini`
- `anthropic/claude-3-haiku`
- `anthropic/claude-3-sonnet`

Check with chutes.ai documentation for the latest available models.

## Validation and Testing

### Test Your Configuration

1. **Start TunaCode**:
   ```bash
   tunacode
   ```

2. **Check Current Model**:
   ```
   /model
   ```

3. **Test with a Simple Query**:
   ```
   Hello, can you confirm which model you are?
   ```

### Troubleshooting Common Issues

#### Connection Errors
- **Problem**: `Connection refused` or timeout errors
- **Solution**: Verify your internet connection and the base URL is correct
- **Test**: `curl https://llm.chutes.ai/v1/models`

#### Authentication Errors
- **Problem**: `401 Unauthorized` or invalid API key
- **Solution**: Double-check your API key is correctly copied
- **Verify**: Ensure no extra spaces or newline characters

#### Model Not Found
- **Problem**: `404 Model not found`
- **Solution**: Verify the exact model name with chutes.ai
- **List models**: `curl -H "Authorization: Bearer YOUR_KEY" https://llm.chutes.ai/v1/models`

#### Base URL Format
- **Correct**: `https://llm.chutes.ai/v1`
- **Incorrect**: `https://llm.chutes.ai/v1/chat/completions`
- **Remember**: TunaCode automatically adds endpoint paths

## Advanced Configuration

### Custom Settings

Adjust these settings for optimal performance:

```json
"settings": {
    "max_retries": 5,           // Reduce for faster failure detection
    "max_iterations": 30,       // Adjust based on task complexity
    "context_window_size": 128000, // Match model's context limit
    "enable_streaming": true    // Enable real-time responses
}
```

### MCP Servers

If you use Model Context Protocol servers:

```json
"mcpServers": {
    "filesystem": {
        "command": "npx",
        "args": ["@modelcontextprotocol/server-filesystem", "/path/to/allowed/directory"]
    }
}
```

## Migration Guide

### From OpenRouter to Chutes.ai

1. **Backup existing config**:
   ```bash
   cp ~/.config/tunacode.json ~/.config/tunacode.json.backup
   ```

2. **Update configuration**:
   ```json
   // Change from:
   "default_model": "openrouter:minimax/minimax-m2"
   "OPENROUTER_API_KEY": "sk-or-v1-..."

   // To:
   "default_model": "openai:MiniMaxAI/MiniMax-M2"
   "OPENAI_API_KEY": "cpk_..."
   "OPENAI_BASE_URL": "https://llm.chutes.ai/v1"
   ```

3. **Test the migration**:
   ```bash
   tunacode --model "openai:MiniMaxAI/MiniMax-M2"
   ```

## Environment Variable Alternative

Instead of editing the config file, you can use environment variables:

```bash
export OPENAI_API_KEY="cpk_your_chutes_key"
export OPENAI_BASE_URL="https://llm.chutes.ai/v1"
tunacode --model "openai:MiniMaxAI/MiniMax-M2"
```

## Summary

The key configuration pattern for TunaCode + Chutes.ai is:

1. **Model format**: `openai:MODEL_NAME` (uses OpenAI client)
2. **API key**: Set `OPENAI_API_KEY` with your chutes.ai key
3. **Base URL**: Set `OPENAI_BASE_URL` to `https://llm.chutes.ai/v1`
4. **Provider prefix**: Use `openai:` prefix even for chutes.ai models

This setup provides a robust, production-ready configuration for using TunaCode with chutes.ai's AI services.