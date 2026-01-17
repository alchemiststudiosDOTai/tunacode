"""Message order validation utilities."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

PART_KIND_SYSTEM_PROMPT: str = "system-prompt"
PART_KIND_TOOL_RETURN: str = "tool-return"
PART_KIND_USER_PROMPT: str = "user-prompt"

MESSAGE_KIND_REQUEST: str = "request"
MESSAGE_KIND_RESPONSE: str = "response"

STATE_START: str = "start"
STATE_REQUESTS: str = "requests"
STATE_RESPONSES: str = "responses"
CATEGORY_UNKNOWN: str = "unknown"

ERROR_EMPTY_SEQUENCE: str = "Message sequence is empty"
ERROR_SYSTEM_PROMPT_POSITION: str = "System prompts must appear before requests"
ERROR_RESPONSE_BEFORE_REQUEST: str = "Responses must follow a request"
ERROR_UNKNOWN_MESSAGE: str = "Unknown message type in sequence"
ERROR_MISSING_REQUESTS: str = "Missing request messages"
ERROR_MISSING_RESPONSES: str = "Missing response messages"
ERROR_SEQUENCE_ENDS_WITH_REQUEST: str = "Sequence ends without a response"
ERROR_MIXED_SYSTEM_AND_REQUEST: str = "Message mixes system and request parts"


class MessageOrderError(ValueError):
    """Raised when message order violates conversation invariants."""


def validate_message_order(messages: Iterable[Any], *, allow_partial: bool = False) -> None:
    """Validate that messages follow the documented request/response order."""
    message_list = list(messages)
    if not message_list:
        raise MessageOrderError(ERROR_EMPTY_SEQUENCE)

    system_prompt_seen = False
    saw_request = False
    saw_response = False
    state = STATE_START

    for message in message_list:
        category = _classify_message(message)
        if category == PART_KIND_SYSTEM_PROMPT:
            if system_prompt_seen or state != STATE_START:
                raise MessageOrderError(ERROR_SYSTEM_PROMPT_POSITION)
            system_prompt_seen = True
            continue

        if category == MESSAGE_KIND_REQUEST:
            saw_request = True
            state = STATE_REQUESTS
            continue

        if category == MESSAGE_KIND_RESPONSE:
            if not saw_request:
                raise MessageOrderError(ERROR_RESPONSE_BEFORE_REQUEST)
            saw_response = True
            state = STATE_RESPONSES
            continue

        raise MessageOrderError(ERROR_UNKNOWN_MESSAGE)

    if not saw_request:
        raise MessageOrderError(ERROR_MISSING_REQUESTS)

    if not saw_response and not allow_partial:
        raise MessageOrderError(ERROR_MISSING_RESPONSES)

    if state == STATE_REQUESTS and not allow_partial:
        raise MessageOrderError(ERROR_SEQUENCE_ENDS_WITH_REQUEST)


def _classify_message(message: Any) -> str:
    """Classify a message as system, request, or response."""
    message_kind = _get_message_kind(message)
    has_system = _message_has_part_kind(message, {PART_KIND_SYSTEM_PROMPT})
    has_request_parts = _message_has_part_kind(
        message, {PART_KIND_USER_PROMPT, PART_KIND_TOOL_RETURN}
    )

    if has_system and has_request_parts:
        raise MessageOrderError(ERROR_MIXED_SYSTEM_AND_REQUEST)

    if has_system:
        return PART_KIND_SYSTEM_PROMPT

    if message_kind == MESSAGE_KIND_RESPONSE:
        return MESSAGE_KIND_RESPONSE

    if message_kind == MESSAGE_KIND_REQUEST or has_request_parts:
        return MESSAGE_KIND_REQUEST

    return CATEGORY_UNKNOWN


def _get_message_kind(message: Any) -> str | None:
    if isinstance(message, dict):
        return message.get("kind")
    return getattr(message, "kind", None)


def _message_has_part_kind(message: Any, expected_kinds: set[str]) -> bool:
    return any(_get_part_kind(part) in expected_kinds for part in _iter_parts(message))


def _iter_parts(message: Any) -> Iterable[Any]:
    parts = message.get("parts") if isinstance(message, dict) else getattr(message, "parts", None)

    if isinstance(parts, list):
        return parts
    return []


def _get_part_kind(part: Any) -> str | None:
    if isinstance(part, dict):
        return part.get("part_kind")
    return getattr(part, "part_kind", None)
