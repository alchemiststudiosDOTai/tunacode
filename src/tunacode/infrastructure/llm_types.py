"""Pydantic-AI specific type re-exports.

This module isolates all pydantic-ai framework dependencies to the
infrastructure layer. Code in other layers should import from here
instead of importing pydantic-ai directly.

NOTE: This is a transitional module. As we migrate to framework-agnostic
abstractions, imports from here should decrease. The goal is to eventually
have only adapter code depend on pydantic-ai directly.
"""

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest as _ModelRequest
from pydantic_ai.messages import ToolReturnPart

# =============================================================================
# Type Re-exports
# =============================================================================
# These provide stable names for pydantic-ai types used throughout the codebase.

# Agent type
PydanticAgent = Agent

# Message part types
MessagePart = ToolReturnPart | Any
ModelRequest = _ModelRequest
ModelResponse = Any

# Agent run types
AgentResponse = Any
MessageHistory = list[Any]
AgentRun = Any

__all__ = [
    "AgentResponse",
    "AgentRun",
    "MessageHistory",
    "MessagePart",
    "ModelRequest",
    "ModelResponse",
    "PydanticAgent",
]
