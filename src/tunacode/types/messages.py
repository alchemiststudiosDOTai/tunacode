"""Serialized message types for session persistence and cleanup."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypedDict


class SerializedMessagePart(TypedDict, total=False):
    """JSON-serialized message part structure."""

    part_kind: str
    tool_call_id: str
    tool_name: str
    args: str | dict[str, object] | None
    content: str
    timestamp: str
    id: str | None
    provider_details: dict[str, object] | None


class SerializedMessage(TypedDict, total=False):
    """JSON-serialized message structure."""

    kind: str
    parts: list[SerializedMessagePart]
    tool_calls: list[SerializedMessagePart]
    instructions: str | None
    run_id: str | None
    metadata: dict[str, object] | None
    usage: dict[str, object]
    model_name: str | None
    timestamp: str | None
    provider_name: str | None
    provider_details: dict[str, object] | None
    provider_response_id: str | None
    finish_reason: str | None


class MessagePartProtocol(Protocol):
    """Protocol for message parts with tool call identifiers."""

    part_kind: str | None
    tool_call_id: str | None


class MessagePartsProtocol(Protocol):
    """Protocol for message objects with parts."""

    parts: Sequence[MessagePartProtocol]


MessagePartLike = SerializedMessagePart | MessagePartProtocol
MessageLike = SerializedMessage | MessagePartsProtocol


__all__ = [
    "MessageLike",
    "MessagePartLike",
    "MessagePartProtocol",
    "MessagePartsProtocol",
    "SerializedMessage",
    "SerializedMessagePart",
]
