"""Agent components package for modular agent functionality.

During the tinyagent migration, we keep this package focused on:

- agent construction + caching
- helper utilities used by the request loop

Legacy pydantic-ai orchestration modules have been deleted.
"""

from .agent_config import get_or_create_agent, invalidate_agent_cache
from .agent_helpers import (
    create_empty_response_message,
    get_recent_tools_context,
    get_tool_description,
    handle_empty_response,
)

__all__ = [
    "get_or_create_agent",
    "invalidate_agent_cache",
    "create_empty_response_message",
    "get_recent_tools_context",
    "get_tool_description",
    "handle_empty_response",
]
