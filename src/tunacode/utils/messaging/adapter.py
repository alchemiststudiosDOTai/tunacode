"""Message adapter for converting between pydantic-ai and canonical formats.

This module provides bidirectional conversion between:
- pydantic-ai message types (ModelRequest, ModelResponse, parts)
- Canonical message types (CanonicalMessage, CanonicalPart)

The adapter is the ONLY place that handles message format polymorphism.
All other code should use canonical types exclusively.

See docs/refactoring/architecture-refactor-plan.md for migration strategy.
"""

from typing import Any

from tunacode.types.canonical import (
    CanonicalMessage,
    CanonicalPart,
    MessageRole,
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
PYDANTIC_PART_KIND_SYSTEM_PROMPT = "system-prompt"
PYDANTIC_PART_KIND_USER_PROMPT = "user-prompt"

PYDANTIC_MESSAGE_KIND_REQUEST = "request"
PYDANTIC_MESSAGE_KIND_RESPONSE = "response"


# =============================================================================
# Attribute Accessors
# =============================================================================
# These handle the dict/object polymorphism in one place.


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Get attribute from dict or object."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _get_parts(message: Any) -> list[Any]:
    """Extract parts list from a message."""
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

    # Text part
    if part_kind == PYDANTIC_PART_KIND_TEXT:
        content = _get_attr(part, "content", "")
        return TextPart(content=str(content))

    # User prompt (treat as text)
    if part_kind == PYDANTIC_PART_KIND_USER_PROMPT:
        content = _get_attr(part, "content", "")
        return TextPart(content=str(content))

    # Tool call
    if part_kind == PYDANTIC_PART_KIND_TOOL_CALL:
        return ToolCallPart(
            tool_call_id=_get_attr(part, "tool_call_id", ""),
            tool_name=_get_attr(part, "tool_name", ""),
            args=_get_attr(part, "args", {}) or {},
        )

    # Tool return
    if part_kind == PYDANTIC_PART_KIND_TOOL_RETURN:
        content = _get_attr(part, "content", "")
        return ToolReturnPart(
            tool_call_id=_get_attr(part, "tool_call_id", ""),
            content=str(content),
        )

    # System prompt
    if part_kind == PYDANTIC_PART_KIND_SYSTEM_PROMPT:
        content = _get_attr(part, "content", "")
        return SystemPromptPart(content=str(content))

    # Unknown part type - log and skip
    return None


def _determine_role(message: Any) -> MessageRole:
    """Determine the role of a message."""
    kind = _get_attr(message, "kind")

    if kind == PYDANTIC_MESSAGE_KIND_REQUEST:
        return MessageRole.USER
    if kind == PYDANTIC_MESSAGE_KIND_RESPONSE:
        return MessageRole.ASSISTANT

    # Fallback: check for role attribute
    role = _get_attr(message, "role")
    if role == "user":
        return MessageRole.USER
    if role == "assistant":
        return MessageRole.ASSISTANT
    if role == "tool":
        return MessageRole.TOOL
    if role == "system":
        return MessageRole.SYSTEM

    # Default to user for unknown
    return MessageRole.USER


# =============================================================================
# Message Conversion: pydantic-ai -> Canonical
# =============================================================================


def to_canonical(message: Any) -> CanonicalMessage:
    """Convert a pydantic-ai message (or dict) to canonical format.

    Handles all the polymorphic message formats:
    - pydantic-ai ModelRequest/ModelResponse objects
    - Serialized dict messages
    - Legacy dict formats with "content" or "thought" keys

    Args:
        message: A pydantic-ai message or dict

    Returns:
        CanonicalMessage with typed parts
    """
    # Handle legacy dict formats first
    if isinstance(message, dict):
        # Legacy thought format
        if "thought" in message:
            content = str(message.get("thought", ""))
            return CanonicalMessage(
                role=MessageRole.ASSISTANT,
                parts=(ThoughtPart(content=content),),
            )

        # Legacy content-only format
        if "content" in message and "parts" not in message and "kind" not in message:
            content = message.get("content", "")
            if isinstance(content, str):
                return CanonicalMessage(
                    role=MessageRole.USER,
                    parts=(TextPart(content=content),),
                )

    # Extract role
    role = _determine_role(message)

    # Extract and convert parts
    raw_parts = _get_parts(message)
    canonical_parts: list[CanonicalPart] = []

    for raw_part in raw_parts:
        converted = _convert_part_to_canonical(raw_part)
        if converted is not None:
            canonical_parts.append(converted)

    # If no parts but has content, create a text part
    if not canonical_parts:
        content = _get_attr(message, "content")
        if content:
            if isinstance(content, str):
                canonical_parts.append(TextPart(content=content))
            elif isinstance(content, list):
                # Nested content (e.g., list of dicts)
                for item in content:
                    if isinstance(item, str):
                        canonical_parts.append(TextPart(content=item))
                    elif isinstance(item, dict) and "text" in item:
                        canonical_parts.append(TextPart(content=str(item["text"])))

    return CanonicalMessage(
        role=role,
        parts=tuple(canonical_parts),
        timestamp=None,  # Could extract from message if available
    )


def to_canonical_list(messages: list[Any]) -> list[CanonicalMessage]:
    """Convert a list of messages to canonical format."""
    return [to_canonical(msg) for msg in messages]


# =============================================================================
# Message Conversion: Canonical -> pydantic-ai
# =============================================================================


def from_canonical(message: CanonicalMessage) -> dict[str, Any]:
    """Convert a canonical message back to dict format for pydantic-ai.

    Note: We return dicts rather than pydantic-ai objects because:
    1. pydantic-ai can accept dict format in message_history
    2. We avoid importing pydantic-ai types here
    3. Dict format is more portable for serialization

    Args:
        message: A CanonicalMessage

    Returns:
        Dict in pydantic-ai compatible format
    """
    parts: list[dict[str, Any]] = []

    for part in message.parts:
        if isinstance(part, TextPart):
            parts.append({
                "part_kind": "text",
                "content": part.content,
            })
        elif isinstance(part, ThoughtPart):
            # Thoughts are internal - convert to text for API
            parts.append({
                "part_kind": "text",
                "content": part.content,
            })
        elif isinstance(part, SystemPromptPart):
            parts.append({
                "part_kind": "system-prompt",
                "content": part.content,
            })
        elif isinstance(part, ToolCallPart):
            parts.append({
                "part_kind": "tool-call",
                "tool_call_id": part.tool_call_id,
                "tool_name": part.tool_name,
                "args": part.args,
            })
        elif isinstance(part, ToolReturnPart):
            parts.append({
                "part_kind": "tool-return",
                "tool_call_id": part.tool_call_id,
                "content": part.content,
            })

    kind = (
        PYDANTIC_MESSAGE_KIND_REQUEST
        if message.role in (MessageRole.USER, MessageRole.SYSTEM)
        else PYDANTIC_MESSAGE_KIND_RESPONSE
    )

    return {
        "kind": kind,
        "parts": parts,
    }


def from_canonical_list(messages: list[CanonicalMessage]) -> list[dict[str, Any]]:
    """Convert a list of canonical messages back to dict format."""
    return [from_canonical(msg) for msg in messages]


# =============================================================================
# Content Extraction (replaces message_utils.get_message_content)
# =============================================================================


def get_content(message: Any) -> str:
    """Extract text content from any message format.

    This is the unified replacement for message_utils.get_message_content().
    Works with:
    - CanonicalMessage
    - pydantic-ai messages
    - Dict messages in any legacy format

    Args:
        message: Any message format

    Returns:
        Concatenated text content
    """
    # If already canonical, use the method
    if isinstance(message, CanonicalMessage):
        return message.get_text_content()

    # Convert to canonical and extract
    canonical = to_canonical(message)
    return canonical.get_text_content()


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
    """Find tool call IDs that have no matching tool return.

    This is a simplified version of what sanitize.py does.
    """
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
    # Conversion functions
    "to_canonical",
    "to_canonical_list",
    "from_canonical",
    "from_canonical_list",
    # Content extraction
    "get_content",
    # Tool call helpers
    "get_tool_call_ids",
    "get_tool_return_ids",
    "find_dangling_tool_calls",
]
