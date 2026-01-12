"""Pydantic-AI type wrappers for TunaCode CLI.

Isolates pydantic-ai dependencies to a single module for easier
migration if the underlying library changes.
"""

from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest as _ModelRequest
from pydantic_ai.messages import ToolReturnPart

DEFAULT_TOKEN_COUNT = 0
USAGE_ATTR_REQUEST_TOKENS = "request_tokens"
USAGE_ATTR_RESPONSE_TOKENS = "response_tokens"
USAGE_ATTR_CACHED_TOKENS = "cached_tokens"

# Re-export with stable names ugly but better thab what we had before
PydanticAgent = Agent
MessagePart = ToolReturnPart | Any
ModelRequest = _ModelRequest
ModelResponse = Any

AgentResponse = Any
MessageHistory = list[Any]
AgentRun = Any


@dataclass(frozen=True, slots=True)
class NormalizedUsage:
    """Normalized usage values for provider-agnostic tracking."""

    request_tokens: int
    response_tokens: int
    cached_tokens: int


def _read_usage_value(usage: Any, attribute: str) -> int:
    raw_value = getattr(usage, attribute, None)
    return int(raw_value or DEFAULT_TOKEN_COUNT)


def normalize_request_usage(usage: Any | None) -> NormalizedUsage | None:
    """Normalize usage objects to a stable shape for internal tracking."""
    if usage is None:
        return None

    return NormalizedUsage(
        request_tokens=_read_usage_value(usage, USAGE_ATTR_REQUEST_TOKENS),
        response_tokens=_read_usage_value(usage, USAGE_ATTR_RESPONSE_TOKENS),
        cached_tokens=_read_usage_value(usage, USAGE_ATTR_CACHED_TOKENS),
    )


__all__ = [
    "AgentResponse",
    "AgentRun",
    "MessageHistory",
    "MessagePart",
    "ModelRequest",
    "ModelResponse",
    "PydanticAgent",
    "NormalizedUsage",
    "normalize_request_usage",
]
