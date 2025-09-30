# Custom Model Provider Setup Guide

This guide explains how to configure custom model providers in tunacode, allowing you to use any OpenAI-compatible API endpoint with your own models.

## Overview

tunacode supports custom model providers through configuration in `~/.tunacode/config.toml`. You can define providers for:
- Commercial AI services (Mistral, Anthropic, etc.)
- Self-hosted models (Ollama, vLLM, etc.)
- Cloud deployments (Azure OpenAI, etc.)
- Proxy services and mock servers

## Configuration File Location

Create or edit `~/.tunacode/config.toml` to add your custom providers.

## Provider Configuration Structure

```toml
[model_providers.your-provider-id]
name = "Display Name"
base_url = "https://your-api.com/v1"
env_key = "YOUR_API_KEY_ENV_VAR"
wire_api = "chat"  # or "responses"
```

## Complete Configuration Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | Friendly display name for the provider |
| `base_url` | String | No | API base URL (defaults to OpenAI) |
| `env_key` | String | No | Environment variable name for API key |
| `env_key_instructions` | String | No | Instructions for getting API key |
| `wire_api` | String | No | Protocol: "chat" or "responses" (default: "responses") |
| `query_params` | Map | No | Additional URL query parameters |
| `http_headers` | Map | No | Static HTTP headers |
| `env_http_headers` | Map | No | Headers from environment variables |
| `request_max_retries` | Number | No | Max HTTP request retries |
| `stream_max_retries` | Number | No | Max streaming connection retries |
| `stream_idle_timeout_ms` | Number | No | Stream idle timeout in milliseconds |
| `requires_openai_auth` | Boolean | No | Requires OpenAI login (default: false) |

## Protocol Types

### `wire_api = "chat"`
- Uses OpenAI Chat Completions API format
- Endpoint: `/chat/completions`
- Standard chat completion requests

### `wire_api = "responses"`
- Uses OpenAI Responses API format
- Endpoint: `/responses`
- Advanced response handling with tools

## Configuration Examples

### Mistral AI
```toml
[model_providers.mistral]
name = "Mistral"
base_url = "https://api.mistral.ai/v1"
env_key = "MISTRAL_API_KEY"
wire_api = "chat"
```

### Anthropic Claude (via proxy)
```toml
[model_providers.anthropic]
name = "Anthropic"
base_url = "https://api.anthropic.com/v1"
env_key = "ANTHROPIC_API_KEY"
wire_api = "chat"
http_headers = { "x-api-key" = "$ANTHROPIC_API_KEY", "anthropic-version" = "2023-06-01" }
```

### Azure OpenAI
```toml
[model_providers.azure]
name = "Azure"
base_url = "https://your-resource.openai.azure.com/openai"
env_key = "AZURE_OPENAI_API_KEY"
query_params = { "api-version" = "2025-04-01-preview" }
wire_api = "responses"
```

### Local Ollama
```toml
[model_providers.ollama]
name = "Ollama"
base_url = "http://localhost:11434/v1"
env_key = "OLLAMA_API_KEY"  # Optional if no auth
wire_api = "chat"
```

### vLLM Server
```toml
[model_providers.vllm]
name = "vLLM"
base_url = "http://localhost:8000/v1"
env_key = "VLLM_API_KEY"  # Optional if no auth
wire_api = "chat"
```

### Custom Proxy
```toml
[model_providers.custom-proxy]
name = "Custom Proxy"
base_url = "https://proxy.yourcompany.com/ai/v1"
env_key = "PROXY_API_KEY"
wire_api = "chat"
query_params = { "model" = "gpt-4", "temperature" = "0.7" }
```

## Environment Variable Setup

### 1. Set API Keys
```bash
# For Mistral
export MISTRAL_API_KEY="your-mistral-key"

# For Azure
export AZURE_OPENAI_API_KEY="your-azure-key"

# For custom provider
export YOUR_API_KEY_ENV_VAR="your-api-key"
```

### 2. Override Built-in Providers
```bash
# Override OpenAI base URL
export OPENAI_BASE_URL="https://custom-openai-endpoint.com/v1"

# Override OSS provider URL
export tunacode_OSS_BASE_URL="http://localhost:8000/v1"
export tunacode_OSS_PORT="8000"
```

## Headers and Authentication

### Static Headers
```toml
[model_providers.your-provider]
http_headers = {
    "Content-Type" = "application/json",
    "User-Agent" = "tunacode/1.0",
    "Authorization" = "Bearer static-token"
}
```

### Environment Variable Headers
```toml
[model_providers.your-provider]
env_http_headers = {
    "Authorization" = "AUTH_TOKEN",
    "X-API-Key" = "API_KEY"
}
```

## Using Your Custom Provider

### 1. Via CLI
```bash
# Use your custom provider
tunacode --model-provider your-provider-id

# Or set as default in config.toml
model_provider = "your-provider-id"
```

### 2. Via Config File
Set your provider as the default in `~/.tunacode/config.toml`:
```toml
model_provider = "your-provider-id"
```

## Advanced Configuration

### Retry Settings
```toml
[model_providers.your-provider]
request_max_retries = 5
stream_max_retries = 3
stream_idle_timeout_ms = 30000
```

### Multiple Query Parameters
```toml
[model_providers.your-provider]
query_params = {
    "api-version" = "2025-04-01",
    "model" = "gpt-4",
    "temperature" = "0.7"
}
```

## Troubleshooting

### Common Issues

1. **API Key Not Found**
   - Ensure the environment variable is set correctly
   - Check for typos in the `env_key` field

2. **URL Not Found**
   - Verify the `base_url` is correct and accessible
   - Check if the API path includes `/v1` or similar

3. **Protocol Mismatch**
   - Ensure `wire_api` matches your provider's expected format
   - Check if your provider uses `/chat/completions` or `/responses`

4. **Authentication Failures**
   - Verify headers are correctly configured
   - Check if your provider uses Bearer tokens or custom headers

### Testing Configuration
```bash
# Test your provider configuration
tunacode --model-provider your-provider-id --help

# Check loaded configuration
tunacode --config
```

## Built-in Providers

tunacode includes two built-in providers that can be overridden:

### OpenAI Provider
```toml
[model_providers.openai]
name = "OpenAI"
wire_api = "responses"
# Override via environment variable:
export OPENAI_BASE_URL="https://custom-openai.com/v1"
```

### OSS Provider
```toml
[model_providers.oss]
name = "gpt-oss"
wire_api = "chat"
# Override via environment variables:
export tunacode_OSS_BASE_URL="http://localhost:11434/v1"
export tunacode_OSS_PORT="11434"
```

## Best Practices

1. **Security**: Never hardcode API keys in config files - use environment variables
2. **Validation**: Test your configuration before using in production
3. **Fallback**: Consider configuring multiple providers for redundancy
4. **Documentation**: Document your custom provider configurations for your team
5. **Version Pinning**: Pin API versions in query parameters for stability

## Support

For issues with custom provider configurations:
1. Check the [troubleshooting section](#troubleshooting)
2. Verify your provider's API documentation
3. Test connectivity to your endpoint
4. Check tunacode logs for detailed error information