"""Message adapter for converting between pydantic-ai and canonical formats.

This module provides bidirectional conversion between:
- pydantic-ai message types (ModelRequest, ModelResponse, parts)
- Canonical message types (CanonicalMessage, CanonicalPart)

The adapter is the ONLY place that handles message format polymorphism.
All other code should use canonical types exclusively.

Tool calls are ONLY in `parts`. The `tool_calls` property on pydantic-ai
objects is a computed property derived from parts - not a separate source.

See docs/refactoring/architecture-refactor-plan.md for migration strategy.
"""

from typing import Any

from tunacode.types.canonical import (
    CanonicalMessage,
    CanonicalPart,
    MessageRole,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThoughtPart,
    ToolCallPart,
    ToolReturnPart,
)

# =============================================================================
# Part Kind Constants (matching pydantic-ai)
# =============================================================================

PYDANTIC_PART_KIND_TEXT = "text"
PYDANTIC_PART_KIND_TOOL_CALL = "tool-call"
PYDANTIC_PART_KIND_TOOL_RETURN = "tool-return"
PYDANTIC_PART_KIND_RETRY_PROMPT = "retry-prompt"
PYDANTIC_PART_KIND_SYSTEM_PROMPT = "system-prompt"
PYDANTIC_PART_KIND_USER_PROMPT = "user-prompt"

PYDANTIC_MESSAGE_KIND_REQUEST = "request"
PYDANTIC_MESSAGE_KIND_RESPONSE = "response"


# =============================================================================
# Attribute Accessors
# =============================================================================


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Get attribute from dict or object."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _get_parts(message: Any) -> list[Any]:
    """Extract parts list from a message.

    Parts is the single source of truth for message content including tool calls.
    """
    parts = _get_attr(message, "parts")
    if parts is None:
        return []
    if isinstance(parts, (list, tuple)):
        return list(parts)
    return []


# =============================================================================
# Part Conversion: pydantic-ai -> Canonical
# =============================================================================


def _convert_part_to_canonical(part: Any) -> CanonicalPart | None:
    """Convert a single pydantic-ai part to canonical format.

    Returns None for unrecognized parts (they are filtered out).
    """
    part_kind = _get_attr(part, "part_kind")

    if part_kind == PYDANTIC_PART_KIND_TEXT:
        content = _get_attr(part, "content", "")
        return TextPart(content=str(content))

    if part_kind == PYDANTIC_PART_KIND_USER_PROMPT:
        content = _get_attr(part, "content", "")
        return TextPart(content=str(content))

    if part_kind == PYDANTIC_PART_KIND_TOOL_CALL:
        return ToolCallPart(
            tool_call_id=_get_attr(part, "tool_call_id", ""),
            tool_name=_get_attr(part, "tool_name", ""),
            args=_get_attr(part, "args", {}),
        )

    if part_kind == PYDANTIC_PART_KIND_TOOL_RETURN:
        content = _get_attr(part, "content", "")
        return ToolReturnPart(
            tool_call_id=_get_attr(part, "tool_call_id", ""),
            content=str(content),
        )

    if part_kind == PYDANTIC_PART_KIND_RETRY_PROMPT:
        content = _get_attr(part, "content", "")
        return RetryPromptPart(
            tool_call_id=_get_attr(part, "tool_call_id", ""),
            tool_name=_get_attr(part, "tool_name", ""),
            content=str(content),
        )

    if part_kind == PYDANTIC_PART_KIND_SYSTEM_PROMPT:
        content = _get_attr(part, "content", "")
        return SystemPromptPart(content=str(content))

    return None


def _determine_role(message: Any) -> MessageRole:
    """Determine the role of a message."""
    kind = _get_attr(message, "kind")

    if kind == PYDANTIC_MESSAGE_KIND_REQUEST:
        return MessageRole.USER
    if kind == PYDANTIC_MESSAGE_KIND_RESPONSE:
        return MessageRole.ASSISTANT

    role = _get_attr(message, "role")
    if role == "user":
        return MessageRole.USER
    if role == "assistant":
        return MessageRole.ASSISTANT
    if role == "tool":
        return MessageRole.TOOL
    if role == "system":
        return MessageRole.SYSTEM

    return MessageRole.USER


# =============================================================================
# Message Conversion: pydantic-ai -> Canonical
# =============================================================================


def to_canonical(message: Any) -> CanonicalMessage:
    """Convert a pydantic-ai message (or dict) to canonical format.

    Handles:
    - pydantic-ai ModelRequest/ModelResponse objects
    - Serialized dict messages with parts
    - Legacy dict formats with "content" or "thought" keys

    Tool calls are extracted from `parts` only. The `tool_calls` property
    on pydantic-ai objects is computed from parts, not a separate source.
    """
    # Handle legacy dict formats first
    if isinstance(message, dict):
        if "thought" in message:
            content = str(message.get("thought", ""))
            return CanonicalMessage(
                role=MessageRole.ASSISTANT,
                parts=(ThoughtPart(content=content),),
            )

        if "content" in message and "parts" not in message and "kind" not in message:
            content = message.get("content", "")
            if isinstance(content, str):
                return CanonicalMessage(
                    role=MessageRole.USER,
                    parts=(TextPart(content=content),),
                )

    role = _determine_role(message)

    # Extract and convert parts - the single source of truth
    raw_parts = _get_parts(message)
    canonical_parts: list[CanonicalPart] = []

    for raw_part in raw_parts:
        converted = _convert_part_to_canonical(raw_part)
        if converted is not None:
            canonical_parts.append(converted)

    # Fallback: if no parts but has content, create a text part
    if not canonical_parts:
        content = _get_attr(message, "content")
        if content:
            if isinstance(content, str):
                canonical_parts.append(TextPart(content=content))
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        canonical_parts.append(TextPart(content=item))
                    elif isinstance(item, dict) and "text" in item:
                        canonical_parts.append(TextPart(content=str(item["text"])))

    return CanonicalMessage(
        role=role,
        parts=tuple(canonical_parts),
        timestamp=None,
    )


def to_canonical_list(messages: list[Any]) -> list[CanonicalMessage]:
    """Convert a list of messages to canonical format."""
    return [to_canonical(msg) for msg in messages]


# =============================================================================
# Message Conversion: Canonical -> pydantic-ai
# =============================================================================


def from_canonical(message: CanonicalMessage) -> dict[str, Any]:
    """Convert a canonical message back to dict format for pydantic-ai."""
    parts: list[dict[str, Any]] = []

    for part in message.parts:
        if isinstance(part, (TextPart, ThoughtPart)):
            parts.append(
                {
                    "part_kind": PYDANTIC_PART_KIND_TEXT,
                    "content": part.content,
                }
            )
        elif isinstance(part, SystemPromptPart):
            parts.append(
                {
                    "part_kind": PYDANTIC_PART_KIND_SYSTEM_PROMPT,
                    "content": part.content,
                }
            )
        elif isinstance(part, ToolCallPart):
            parts.append(
                {
                    "part_kind": PYDANTIC_PART_KIND_TOOL_CALL,
                    "tool_call_id": part.tool_call_id,
                    "tool_name": part.tool_name,
                    "args": part.args,
                }
            )
        elif isinstance(part, ToolReturnPart):
            parts.append(
                {
                    "part_kind": PYDANTIC_PART_KIND_TOOL_RETURN,
                    "tool_call_id": part.tool_call_id,
                    "content": part.content,
                }
            )
        elif isinstance(part, RetryPromptPart):
            parts.append(
                {
                    "part_kind": PYDANTIC_PART_KIND_RETRY_PROMPT,
                    "tool_call_id": part.tool_call_id,
                    "tool_name": part.tool_name,
                    "content": part.content,
                }
            )

    kind = (
        PYDANTIC_MESSAGE_KIND_REQUEST
        if message.role in (MessageRole.USER, MessageRole.SYSTEM)
        else PYDANTIC_MESSAGE_KIND_RESPONSE
    )

    return {"kind": kind, "parts": parts}


def from_canonical_list(messages: list[CanonicalMessage]) -> list[dict[str, Any]]:
    """Convert a list of canonical messages back to dict format."""
    return [from_canonical(msg) for msg in messages]


# =============================================================================
# Content Extraction
# =============================================================================


def get_content(message: Any) -> str:
    """Extract text content from any message format.

    Replacement for legacy message content extraction.
    """
    if isinstance(message, CanonicalMessage):
        return message.get_text_content()
    return to_canonical(message).get_text_content()


# =============================================================================
# Tool Call Extraction
# =============================================================================


def get_tool_call_ids(message: Any) -> set[str]:
    """Extract all tool call IDs from a message."""
    if isinstance(message, CanonicalMessage):
        return message.get_tool_call_ids()
    return to_canonical(message).get_tool_call_ids()


def get_tool_return_ids(message: Any) -> set[str]:
    """Extract all tool return IDs from a message."""
    if isinstance(message, CanonicalMessage):
        return message.get_tool_return_ids()
    return to_canonical(message).get_tool_return_ids()


def find_dangling_tool_calls(messages: list[Any]) -> set[str]:
    """Find tool call IDs that have no matching tool return."""
    call_ids: set[str] = set()
    return_ids: set[str] = set()

    for msg in messages:
        call_ids.update(get_tool_call_ids(msg))
        return_ids.update(get_tool_return_ids(msg))

    return call_ids - return_ids


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Conversion
    "to_canonical",
    "to_canonical_list",
    "from_canonical",
    "from_canonical_list",
    # Content extraction
    "get_content",
    "get_tool_call_ids",
    "get_tool_return_ids",
    "find_dangling_tool_calls",
    # Low-level accessors (for internal modules like sanitize.py)
    "_get_attr",
    "_get_parts",
]
