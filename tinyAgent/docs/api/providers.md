# Providers

LLM provider implementations that satisfy the `StreamFn` protocol.

## OpenRouter Provider

```python
from tinyagent import OpenRouterModel, stream_openrouter
```

OpenRouter provides unified access to multiple LLM providers through a single API.

### OpenRouterModel
```python
@dataclass
class OpenRouterModel(Model):
    provider: str = "openrouter"
    id: str = "anthropic/claude-3.5-sonnet"
    api: str = "openrouter"
```

Model configuration for OpenRouter.

**Common Model IDs**:
- `anthropic/claude-3.5-sonnet`
- `anthropic/claude-3.5-haiku`
- `anthropic/claude-3-opus`
- `openai/gpt-4o`
- `openai/gpt-4o-mini`
- `google/gemini-pro-1.5`

### stream_openrouter
```python
async def stream_openrouter(
    model: Model,
    context: Context,
    options: SimpleStreamOptions,
) -> OpenRouterStreamResponse
```

Stream a response from OpenRouter.

**API Key Resolution**:
1. `options["api_key"]`
2. `OPENROUTER_API_KEY` environment variable

**Raises**: `ValueError` if no API key found

**Features**:
- SSE streaming via httpx
- Text delta streaming
- Tool call extraction (streaming JSON parsing)
- Automatic message format conversion (OpenAI-compatible)

**Example**:
```python
from tinyagent import Agent, AgentOptions, OpenRouterModel, stream_openrouter

agent = Agent(AgentOptions(stream_fn=stream_openrouter))
agent.set_model(OpenRouterModel(id="anthropic/claude-3.5-sonnet"))
agent.set_system_prompt("You are a helpful assistant.")

response = await agent.prompt_text("What is the meaning of life?")
```

### OpenRouterStreamResponse
```python
class OpenRouterStreamResponse:
    async def result(self) -> AssistantMessage
    def __aiter__(self) -> AsyncIterator[AssistantMessageEvent]
```

Response object that implements the `StreamResponse` protocol.

## Alchemy Provider

```python
from tinyagent.alchemy_provider import (
    OpenAICompatModel,
    stream_alchemy_openai_completions,
)
```

Rust-based provider using the `alchemy-llm` crate via PyO3 bindings.

### OpenAICompatModel
```python
@dataclass
class OpenAICompatModel(Model):
    provider: str = "openrouter"
    id: str = "moonshotai/kimi-k2.5"
    api: str = "openai-completions"

    # Additional fields for Rust binding
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    name: str | None = None
    headers: dict[str, str] | None = None
    context_window: int = 128_000
    max_tokens: int = 4096
    reasoning: bool = False
```

Model configuration for OpenAI-compatible endpoints via Rust.

### stream_alchemy_openai_completions
```python
async def stream_alchemy_openai_completions(
    model: Model,
    context: Context,
    options: SimpleStreamOptions,
) -> AlchemyStreamResponse
```

Stream using the Rust alchemy-llm implementation.

**Requirements**:
```bash
pip install maturin
cd bindings/alchemy_llm_py
maturin develop
```

**Limitations**:
- Only OpenAI-compatible `/chat/completions` streaming
- Image blocks not supported
- Uses blocking `next_event()` in thread pool (more overhead than native async)

**When to Use**:
- High-throughput scenarios where Rust performance matters
- Consistent behavior with Rust-based services

## Proxy Provider

```python
from tinyagent import (
    ProxyStreamOptions,
    ProxyStreamResponse,
    stream_proxy,
    create_proxy_stream,
    parse_streaming_json,
)
```

Client for apps that route LLM calls through a proxy server.

**Use Case**: Web applications where the server manages:
- API keys
- Provider selection
- Request logging/auditing
- Rate limiting

### ProxyStreamOptions
```python
@dataclass
class ProxyStreamOptions:
    auth_token: str          # Authentication with proxy
    proxy_url: str           # Base URL of proxy server
    temperature: float | None = None
    max_tokens: int | None = None
    reasoning: JsonValue | None = None
    signal: Callable[[], bool] | None = None  # Cancellation check
```

### stream_proxy
```python
async def stream_proxy(
    model: Model,
    context: Context,
    options: ProxyStreamOptions,
) -> ProxyStreamResponse
```

Stream function compatible with the agent loop.

Posts to `{proxy_url}/api/stream` with SSE response handling.

### create_proxy_stream
```python
async def create_proxy_stream(
    model: Model,
    context: Context,
    auth_token: str,
    proxy_url: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    reasoning: JsonValue | None = None,
    signal: Callable[[], bool] | None = None,
) -> ProxyStreamResponse
```

Convenience helper that creates options and calls `stream_proxy`.

### ProxyStreamResponse
```python
class ProxyStreamResponse:
    async def result(self) -> AssistantMessage
    def __aiter__(self) -> AsyncIterator[AssistantMessageEvent]
```

Implements `StreamResponse` protocol for proxy SSE streams.

### parse_streaming_json
```python
def parse_streaming_json(json_str: str) -> JsonObject | None
```

Parse partial JSON from a streaming response.

Handles incomplete JSON by counting braces and appending closing braces.

**Example**:
```python
# Partial JSON from streaming tool arguments
partial = '{"query": "hello'  # Missing closing quote and brace
result = parse_streaming_json(partial)
# Returns: {"query": "hello"} or None if unparseable
```

## Creating Custom Providers

To implement a new provider, create a function matching `StreamFn`:

```python
from tinyagent import StreamResponse, Model, Context, SimpleStreamOptions

async def my_provider(
    model: Model,
    context: Context,
    options: SimpleStreamOptions,
) -> StreamResponse:
    # 1. Convert messages to provider format
    # 2. Make streaming request
    # 3. Yield AssistantMessageEvent objects
    # 4. Return final AssistantMessage
    ...
```

### StreamResponse Protocol

Your response object must implement:

```python
class MyStreamResponse:
    async def result(self) -> AssistantMessage:
        """Return the final complete message."""
        ...

    def __aiter__(self):
        """Return async iterator."""
        ...

    async def __anext__(self) -> AssistantMessageEvent:
        """Yield next event or raise StopAsyncIteration."""
        ...
```

### AssistantMessageEvent Types

Your provider should emit these event types:

- `start`: Streaming begins
- `text_start`, `text_delta`, `text_end`: Text content
- `thinking_start`, `thinking_delta`, `thinking_end`: Reasoning content
- `tool_call_start`, `tool_call_delta`, `tool_call_end`: Tool calls
- `done`: Streaming complete
- `error`: Error occurred

Each event should include `partial`: the current `AssistantMessage` being built.
