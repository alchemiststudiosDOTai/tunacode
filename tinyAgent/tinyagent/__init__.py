"""TinyAgent Python.

A small agent framework for building LLM-powered applications.
"""

from .agent import Agent, AgentOptions, default_convert_to_llm, extract_text
from .agent_loop import (
    agent_loop,
    agent_loop_continue,
    create_agent_stream,
    stream_assistant_response,
    stream_simple,
)
from .agent_tool_execution import (
    execute_tool_calls,
    skip_tool_call,
    validate_tool_arguments,
)
from .agent_types import (
    AgentContext,
    AgentEndEvent,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentStartEvent,
    AgentState,
    AgentTool,
    AgentToolResult,
    AgentToolUpdateCallback,
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    CustomAgentMessage,
    EventStream,
    ImageContent,
    Message,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    Model,
    SimpleStreamOptions,
    StreamFn,
    StreamResponse,
    TextContent,
    ThinkingLevel,
    Tool,
    ToolCall,
    ToolCallContent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolResultMessage,
    TurnEndEvent,
    TurnStartEvent,
    UserMessage,
)
from .openrouter_provider import OpenRouterModel, stream_openrouter
from .proxy import ProxyStreamOptions, ProxyStreamResponse, create_proxy_stream, stream_proxy
from .proxy_event_handlers import parse_streaming_json

__all__ = [
    # OpenRouter
    "OpenRouterModel",
    "stream_openrouter",
    # Agent
    "Agent",
    "AgentOptions",
    "default_convert_to_llm",
    "extract_text",
    # Agent loop
    "agent_loop",
    "agent_loop_continue",
    "create_agent_stream",
    "stream_assistant_response",
    "stream_simple",
    # Tool execution
    "execute_tool_calls",
    "skip_tool_call",
    "validate_tool_arguments",
    # Types
    "ThinkingLevel",
    "TextContent",
    "ImageContent",
    "ToolCall",
    "ToolCallContent",
    "UserMessage",
    "AssistantMessage",
    "ToolResultMessage",
    "CustomAgentMessage",
    "Message",
    "AgentMessage",
    "AgentToolResult",
    "Tool",
    "AgentTool",
    "AgentToolUpdateCallback",
    "Context",
    "AgentContext",
    "Model",
    "SimpleStreamOptions",
    "AssistantMessageEvent",
    "StreamResponse",
    "AgentStartEvent",
    "AgentEndEvent",
    "TurnStartEvent",
    "TurnEndEvent",
    "MessageStartEvent",
    "MessageUpdateEvent",
    "MessageEndEvent",
    "ToolExecutionStartEvent",
    "ToolExecutionUpdateEvent",
    "ToolExecutionEndEvent",
    "AgentEvent",
    "AgentLoopConfig",
    "AgentState",
    "EventStream",
    "StreamFn",
    # Proxy
    "ProxyStreamOptions",
    "ProxyStreamResponse",
    "stream_proxy",
    "create_proxy_stream",
    "parse_streaming_json",
]
