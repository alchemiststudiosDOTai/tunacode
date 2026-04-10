"""Agent components package for modular agent functionality.

During the tinyagent migration, we keep this package focused on:

- agent construction + caching
- helper utilities used by the request loop

Legacy pydantic-ai orchestration modules have been deleted.
"""

from .agent_config import get_or_create_agent, invalidate_agent_cache  # noqa: F401
from .agent_helpers import (  # noqa: F401
    get_recent_tools_context,
    get_tool_description,
)
