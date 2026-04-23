"""Message helpers for tinyagent message models and JSON payloads.

TunaCode stores history as typed tinyagent messages in memory and as tinyagent
JSON dictionaries at persistence boundaries.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeAlias, cast

from tinyagent.agent_types import AgentMessage, JsonObject

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
KEY_URL: str = "url"
KEY_TOOL_CALL_ID: str = "tool_call_id"
KEY_ID: str = "id"

DEFAULT_IMAGE_PLACEHOLDER: str = "[image]"

MESSAGE_PAYLOAD: TypeAlias = JsonObject
MESSAGE_INPUT: TypeAlias = AgentMessage | MESSAGE_PAYLOAD


def _coerce_agent_message_dict(message: MESSAGE_INPUT) -> dict[str, Any]:
    if isinstance(message, dict):
        return cast(dict[str, Any], message)

    return message.model_dump(exclude_none=True)


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
            continue

        raise ValueError(f"Unsupported content item type: {item_type!r}")

    return " ".join(segments)


def _validate_role(role: str) -> None:
    if role not in {ROLE_USER, ROLE_ASSISTANT, ROLE_SYSTEM, ROLE_TOOL_RESULT, ROLE_TOOL}:
        raise ValueError(f"Unsupported agent message role: {role!r}")


def to_canonical(message: MESSAGE_INPUT) -> dict[str, Any]:
    """Return a normalized tinyagent JSON payload for compatibility callers."""

    msg = _coerce_agent_message_dict(message)
    _validate_role(_coerce_role(msg))
    return msg


def to_canonical_list(messages: Sequence[MESSAGE_INPUT]) -> list[dict[str, Any]]:
    """Return normalized tinyagent JSON payloads for compatibility callers."""

    return [to_canonical(msg) for msg in messages]


def from_canonical(message: MESSAGE_PAYLOAD) -> dict[str, Any]:
    """Return a tinyagent-style dict from a compatibility payload."""

    msg = _coerce_agent_message_dict(message)
    _validate_role(_coerce_role(msg))
    return msg


def from_canonical_list(messages: list[MESSAGE_PAYLOAD]) -> list[dict[str, Any]]:
    """Return tinyagent-style dict messages from compatibility payloads."""

    return [from_canonical(msg) for msg in messages]


def get_content(message: MESSAGE_INPUT) -> str:
    """Extract normalized text content from any supported message representation."""

    msg = _coerce_agent_message_dict(message)
    role = _coerce_role(msg)
    _validate_role(role)
    return _content_items_to_text(_coerce_content_items(msg))


def get_tool_call_ids(message: MESSAGE_INPUT) -> set[str]:
    """Return tool call IDs present in an assistant message."""

    msg = _coerce_agent_message_dict(message)
    if _coerce_role(msg) != ROLE_ASSISTANT:
        return set()

    call_ids: set[str] = set()
    for raw_item in _coerce_content_items(msg):
        item = _coerce_content_item(raw_item)
        if item.get(KEY_TYPE) != CONTENT_TYPE_TOOL_CALL:
            continue
        tool_call_id = item.get(KEY_ID)
        if isinstance(tool_call_id, str) and tool_call_id:
            call_ids.add(tool_call_id)

    return call_ids


def get_tool_return_ids(message: MESSAGE_INPUT) -> set[str]:
    """Return tool result IDs present in a tool result message."""

    msg = _coerce_agent_message_dict(message)
    if _coerce_role(msg) not in TOOL_ROLES:
        return set()

    tool_call_id = msg.get(KEY_TOOL_CALL_ID)
    if isinstance(tool_call_id, str) and tool_call_id:
        return {tool_call_id}

    return set()


def find_dangling_tool_calls(messages: Sequence[MESSAGE_INPUT]) -> set[str]:
    """Return tool_call_ids that do not have matching tool_result messages."""

    call_ids: set[str] = set()
    return_ids: set[str] = set()

    for msg in messages:
        call_ids.update(get_tool_call_ids(msg))
        return_ids.update(get_tool_return_ids(msg))

    return call_ids - return_ids
