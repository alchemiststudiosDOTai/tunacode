"""Message adapter for converting between tinyagent messages and canonical types.

TunaCode stores conversation history as tinyagent-style ``AgentMessage`` dicts.
The supported shapes are:

- User message::

    {"role": "user", "content": [{"type": "text", "text": "..."}], ...}

- Assistant message::

    {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "..."},
            {"type": "thinking", "thinking": "..."},
            {"type": "tool_call", "id": "...", "name": "...", "arguments": {...}},
        ],
        ...
    }

- Tool result message::

    {
        "role": "tool_result",
        "tool_call_id": "...",
        "tool_name": "...",
        "content": [{"type": "text", "text": "..."}],
        ...
    }

This module converts those messages into TunaCode's internal canonical dataclasses
(``CanonicalMessage`` / ``CanonicalPart``) for normalization and tool-history
utilities.

Legacy pydantic-ai message formats are intentionally **not** supported.
"""

from __future__ import annotations

from typing import Any, cast

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

# -----------------------------------------------------------------------------
# tinyagent message constants
# -----------------------------------------------------------------------------

KEY_ROLE: str = "role"
KEY_CONTENT: str = "content"
KEY_TYPE: str = "type"

ROLE_USER: str = "user"
ROLE_ASSISTANT: str = "assistant"
ROLE_SYSTEM: str = "system"
ROLE_TOOL_RESULT: str = "tool_result"
ROLE_TOOL: str = "tool"

TOOL_ROLES: set[str] = {ROLE_TOOL_RESULT, ROLE_TOOL}

CONTENT_TYPE_TEXT: str = "text"
CONTENT_TYPE_IMAGE: str = "image"
CONTENT_TYPE_THINKING: str = "thinking"
CONTENT_TYPE_TOOL_CALL: str = "tool_call"

KEY_TEXT: str = "text"
KEY_THINKING: str = "thinking"
KEY_ID: str = "id"
KEY_NAME: str = "name"
KEY_ARGUMENTS: str = "arguments"
KEY_URL: str = "url"

KEY_TOOL_CALL_ID: str = "tool_call_id"

TEXT_SIGNATURE_KEY: str = "text_signature"
THINKING_SIGNATURE_KEY: str = "thinking_signature"
PARTIAL_JSON_KEY: str = "partial_json"

DEFAULT_PARTIAL_JSON: str = ""
DEFAULT_IMAGE_PLACEHOLDER: str = "[image]"

ROLE_TO_CANONICAL: dict[str, MessageRole] = {
    ROLE_USER: MessageRole.USER,
    ROLE_ASSISTANT: MessageRole.ASSISTANT,
    ROLE_SYSTEM: MessageRole.SYSTEM,
    ROLE_TOOL_RESULT: MessageRole.TOOL,
    ROLE_TOOL: MessageRole.TOOL,
}

CANONICAL_TO_ROLE: dict[MessageRole, str] = {
    MessageRole.USER: ROLE_USER,
    MessageRole.ASSISTANT: ROLE_ASSISTANT,
    MessageRole.SYSTEM: ROLE_SYSTEM,
    MessageRole.TOOL: ROLE_TOOL_RESULT,
}


# -----------------------------------------------------------------------------
# low-level helpers
# -----------------------------------------------------------------------------


def _coerce_role(message: dict[str, Any]) -> str:
    role = message.get(KEY_ROLE)
    if not isinstance(role, str) or not role:
        raise TypeError("Agent message is missing a non-empty 'role' string")
    return role


def _coerce_content_items(message: dict[str, Any]) -> list[Any]:
    content = message.get(KEY_CONTENT)
    if content is None:
        return []
    if isinstance(content, list):
        return content
    raise TypeError(f"Agent message '{KEY_CONTENT}' must be a list, got {type(content).__name__}")


def _coerce_content_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise TypeError(f"Content item must be a dict, got {type(item).__name__}")
    return item


def _coerce_text_item(item: dict[str, Any]) -> str:
    text_value = item.get(KEY_TEXT, "")
    return text_value if isinstance(text_value, str) else str(text_value)


def _coerce_thinking_item(item: dict[str, Any]) -> str:
    thinking_value = item.get(KEY_THINKING, "")
    return thinking_value if isinstance(thinking_value, str) else str(thinking_value)


def _coerce_image_item(item: dict[str, Any]) -> str:
    url = item.get(KEY_URL)
    if isinstance(url, str) and url:
        return url
    return DEFAULT_IMAGE_PLACEHOLDER


def _coerce_tool_call_item(item: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    tool_call_id = item.get(KEY_ID)
    if not isinstance(tool_call_id, str) or not tool_call_id:
        raise TypeError("tool_call content item is missing non-empty 'id'")

    tool_name = item.get(KEY_NAME)
    if not isinstance(tool_name, str) or not tool_name:
        raise TypeError("tool_call content item is missing non-empty 'name'")

    arguments = item.get(KEY_ARGUMENTS, {})
    if not isinstance(arguments, dict):
        raise TypeError(
            f"tool_call '{KEY_ARGUMENTS}' must be a dict, got {type(arguments).__name__}"
        )

    return tool_call_id, tool_name, cast(dict[str, Any], arguments)


def _content_items_to_text(content_items: list[Any]) -> str:
    segments: list[str] = []

    for raw_item in content_items:
        if raw_item is None:
            continue

        item = _coerce_content_item(raw_item)
        item_type = item.get(KEY_TYPE)

        if item_type == CONTENT_TYPE_TEXT:
            segments.append(_coerce_text_item(item))
            continue

        if item_type == CONTENT_TYPE_THINKING:
            segments.append(_coerce_thinking_item(item))
            continue

        if item_type == CONTENT_TYPE_IMAGE:
            segments.append(_coerce_image_item(item))
            continue

        if item_type == CONTENT_TYPE_TOOL_CALL:
            # Tool calls are not text content.
            continue

        raise ValueError(f"Unsupported content item type: {item_type!r}")

    return " ".join(segments)


# -----------------------------------------------------------------------------
# Canonical conversion
# -----------------------------------------------------------------------------


def _to_canonical_tool_message(message: dict[str, Any]) -> CanonicalMessage:
    tool_call_id = message.get(KEY_TOOL_CALL_ID)
    if not isinstance(tool_call_id, str) or not tool_call_id:
        raise TypeError("tool_result message is missing non-empty 'tool_call_id'")

    content_text = _content_items_to_text(_coerce_content_items(message))
    parts: tuple[CanonicalPart, ...] = (
        ToolReturnPart(tool_call_id=tool_call_id, content=content_text),
    )
    return CanonicalMessage(role=MessageRole.TOOL, parts=parts, timestamp=None)


def _system_content_item_to_part(item_type: object, item: dict[str, Any]) -> CanonicalPart:
    if item_type == CONTENT_TYPE_TEXT:
        return SystemPromptPart(content=_coerce_text_item(item))

    if item_type == CONTENT_TYPE_IMAGE:
        return SystemPromptPart(content=_coerce_image_item(item))

    raise ValueError(f"System message content must be text/image, got: {item_type!r}")


def _non_system_content_item_to_part(item_type: object, item: dict[str, Any]) -> CanonicalPart:
    if item_type == CONTENT_TYPE_TEXT:
        return TextPart(content=_coerce_text_item(item))

    if item_type == CONTENT_TYPE_THINKING:
        return ThoughtPart(content=_coerce_thinking_item(item))

    if item_type == CONTENT_TYPE_IMAGE:
        return TextPart(content=_coerce_image_item(item))

    if item_type == CONTENT_TYPE_TOOL_CALL:
        tool_call_id, tool_name, args = _coerce_tool_call_item(item)
        return ToolCallPart(tool_call_id=tool_call_id, tool_name=tool_name, args=args)

    raise ValueError(f"Unsupported content item type: {item_type!r}")


def _content_items_to_parts(
    *,
    canonical_role: MessageRole,
    content_items: list[Any],
) -> tuple[CanonicalPart, ...]:
    parts: list[CanonicalPart] = []

    for raw_item in content_items:
        if raw_item is None:
            continue

        item = _coerce_content_item(raw_item)
        item_type = item.get(KEY_TYPE)

        if canonical_role == MessageRole.SYSTEM:
            parts.append(_system_content_item_to_part(item_type, item))
            continue

        parts.append(_non_system_content_item_to_part(item_type, item))

    return tuple(parts)


def to_canonical(message: Any) -> CanonicalMessage:
    """Convert a tinyagent message dict to :class:`~tunacode.types.canonical.CanonicalMessage`."""

    if isinstance(message, CanonicalMessage):
        return message

    if not isinstance(message, dict):
        raise TypeError(f"Unsupported message type: {type(message).__name__}")

    msg = cast(dict[str, Any], message)
    role_raw = _coerce_role(msg)

    canonical_role = ROLE_TO_CANONICAL.get(role_raw)
    if canonical_role is None:
        raise ValueError(f"Unsupported agent message role: {role_raw!r}")

    if role_raw in TOOL_ROLES:
        return _to_canonical_tool_message(msg)

    content_items = _coerce_content_items(msg)
    parts = _content_items_to_parts(
        canonical_role=canonical_role,
        content_items=content_items,
    )

    return CanonicalMessage(role=canonical_role, parts=parts, timestamp=None)


def to_canonical_list(messages: list[Any]) -> list[CanonicalMessage]:
    """Convert a list of messages to canonical format."""

    return [to_canonical(msg) for msg in messages]


def _tool_message_from_canonical(message: CanonicalMessage) -> dict[str, Any]:
    tool_return_parts = [p for p in message.parts if isinstance(p, ToolReturnPart)]
    if len(tool_return_parts) != 1:
        raise ValueError(
            "Canonical TOOL messages must contain exactly one ToolReturnPart "
            f"(got {len(tool_return_parts)})"
        )

    part = tool_return_parts[0]
    return {
        KEY_ROLE: ROLE_TOOL_RESULT,
        KEY_TOOL_CALL_ID: part.tool_call_id,
        KEY_CONTENT: [
            {
                KEY_TYPE: CONTENT_TYPE_TEXT,
                KEY_TEXT: part.content,
                TEXT_SIGNATURE_KEY: None,
            }
        ],
        "details": {},
        "is_error": False,
    }


def _canonical_part_to_content_item(
    *,
    message_role: MessageRole,
    part: CanonicalPart,
) -> dict[str, Any]:
    if isinstance(part, TextPart):
        return {
            KEY_TYPE: CONTENT_TYPE_TEXT,
            KEY_TEXT: part.content,
            TEXT_SIGNATURE_KEY: None,
        }

    if isinstance(part, ThoughtPart):
        return {
            KEY_TYPE: CONTENT_TYPE_THINKING,
            KEY_THINKING: part.content,
            THINKING_SIGNATURE_KEY: None,
        }

    if isinstance(part, SystemPromptPart):
        if message_role != MessageRole.SYSTEM:
            raise ValueError("SystemPromptPart is only valid for SYSTEM messages")

        return {
            KEY_TYPE: CONTENT_TYPE_TEXT,
            KEY_TEXT: part.content,
            TEXT_SIGNATURE_KEY: None,
        }

    if isinstance(part, ToolCallPart):
        if message_role != MessageRole.ASSISTANT:
            raise ValueError("ToolCallPart is only valid for ASSISTANT messages")

        return {
            KEY_TYPE: CONTENT_TYPE_TOOL_CALL,
            KEY_ID: part.tool_call_id,
            KEY_NAME: part.tool_name,
            KEY_ARGUMENTS: part.args,
            PARTIAL_JSON_KEY: DEFAULT_PARTIAL_JSON,
        }

    if isinstance(part, RetryPromptPart):
        # Retry prompts are a legacy abstraction; represent them as text.
        return {
            KEY_TYPE: CONTENT_TYPE_TEXT,
            KEY_TEXT: part.content,
            TEXT_SIGNATURE_KEY: None,
        }

    if isinstance(part, ToolReturnPart):
        raise ValueError("ToolReturnPart must be wrapped in a TOOL message")

    raise TypeError(f"Unsupported canonical part type: {type(part).__name__}")


def from_canonical(message: CanonicalMessage) -> dict[str, Any]:
    """Convert a canonical message back into a tinyagent-style dict."""

    role = CANONICAL_TO_ROLE.get(message.role)
    if role is None:
        raise ValueError(f"Unsupported canonical role: {message.role!r}")

    if message.role == MessageRole.TOOL:
        return _tool_message_from_canonical(message)

    content = [
        _canonical_part_to_content_item(message_role=message.role, part=part)
        for part in message.parts
    ]

    return {KEY_ROLE: role, KEY_CONTENT: content}


def from_canonical_list(messages: list[CanonicalMessage]) -> list[dict[str, Any]]:
    """Convert a list of canonical messages back to tinyagent dict messages."""

    return [from_canonical(msg) for msg in messages]


# -----------------------------------------------------------------------------
# Extraction helpers
# -----------------------------------------------------------------------------


def get_content(message: Any) -> str:
    """Extract normalized text content from any supported message representation."""

    if isinstance(message, CanonicalMessage):
        return message.get_text_content()

    canonical = to_canonical(message)
    return canonical.get_text_content()


def get_tool_call_ids(message: Any) -> set[str]:
    """Return tool call IDs present in a message."""

    canonical = to_canonical(message)
    return canonical.get_tool_call_ids()


def get_tool_return_ids(message: Any) -> set[str]:
    """Return tool return IDs present in a message."""

    canonical = to_canonical(message)
    return canonical.get_tool_return_ids()


def find_dangling_tool_calls(messages: list[Any]) -> set[str]:
    """Return tool_call_ids that do not have matching tool_result messages."""

    call_ids: set[str] = set()
    return_ids: set[str] = set()

    for msg in messages:
        canonical = to_canonical(msg)
        call_ids.update(canonical.get_tool_call_ids())
        return_ids.update(canonical.get_tool_return_ids())

    return call_ids - return_ids


__all__ = [
    "to_canonical",
    "to_canonical_list",
    "from_canonical",
    "from_canonical_list",
    "get_content",
    "get_tool_call_ids",
    "get_tool_return_ids",
    "find_dangling_tool_calls",
]
