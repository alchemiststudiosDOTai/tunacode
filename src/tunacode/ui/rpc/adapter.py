"""Adapters between runtime events/messages and RPC wire payloads."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from tinyagent.agent_types import AgentMessage, AgentToolResult

from tunacode.types.runtime_events import (
    AgentEndRuntimeEvent,
    AgentStartRuntimeEvent,
    CompactionStateChangedRuntimeEvent,
    MessageEndRuntimeEvent,
    MessageStartRuntimeEvent,
    MessageUpdateRuntimeEvent,
    NoticeRuntimeEvent,
    RuntimeEvent,
    ToolExecutionEndRuntimeEvent,
    ToolExecutionStartRuntimeEvent,
    ToolExecutionUpdateRuntimeEvent,
    TurnEndRuntimeEvent,
    TurnStartRuntimeEvent,
)


def serialize_agent_message(message: AgentMessage) -> dict[str, Any]:
    """Serialize a tinyagent message model for the wire boundary."""
    return cast(dict[str, Any], message.model_dump(exclude_none=True))


def serialize_messages(messages: Sequence[AgentMessage]) -> list[dict[str, Any]]:
    """Serialize tinyagent messages for protocol responses/events."""
    return [serialize_agent_message(message) for message in messages]


def serialize_tool_result(result: AgentToolResult | None) -> dict[str, Any] | None:
    """Serialize an AgentToolResult into a plain JSON-ready mapping."""
    if result is None:
        return None

    return {
        "content": [item.model_dump(exclude_none=True) for item in result.content],
        "details": result.details,
    }


def _serialize_message_payload(
    *,
    event_type: str,
    message: AgentMessage | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": event_type}
    if message is not None:
        payload["message"] = serialize_agent_message(message)
    return payload


def _serialize_turn_end_event(event: TurnEndRuntimeEvent) -> dict[str, Any]:
    payload = _serialize_message_payload(event_type=event.type, message=event.message)
    payload["toolResults"] = serialize_messages(event.tool_results)
    return payload


def _serialize_message_update_event(event: MessageUpdateRuntimeEvent) -> dict[str, Any]:
    payload = _serialize_message_payload(event_type=event.type, message=event.message)
    if event.assistant_message_event is not None:
        payload["assistantMessageEvent"] = event.assistant_message_event.model_dump(
            exclude_none=True
        )
    return payload


def _serialize_tool_start_event(event: ToolExecutionStartRuntimeEvent) -> dict[str, Any]:
    return {
        "type": event.type,
        "toolCallId": event.tool_call_id,
        "toolName": event.tool_name,
        "args": event.args,
    }


def _serialize_tool_update_event(event: ToolExecutionUpdateRuntimeEvent) -> dict[str, Any]:
    payload = _serialize_tool_start_event(
        ToolExecutionStartRuntimeEvent(
            tool_call_id=event.tool_call_id,
            tool_name=event.tool_name,
            args=event.args,
        )
    )
    payload["type"] = event.type
    partial_result = serialize_tool_result(event.partial_result)
    if partial_result is not None:
        payload["partialResult"] = partial_result
    return payload


def _serialize_tool_end_event(event: ToolExecutionEndRuntimeEvent) -> dict[str, Any]:
    payload = _serialize_tool_start_event(
        ToolExecutionStartRuntimeEvent(
            tool_call_id=event.tool_call_id,
            tool_name=event.tool_name,
            args=event.args,
        )
    )
    payload["type"] = event.type
    payload["isError"] = event.is_error
    result = serialize_tool_result(event.result)
    if result is not None:
        payload["result"] = result
    if event.duration_ms is not None:
        payload["durationMs"] = event.duration_ms
    return payload


def _wire_from_agent_or_turn_event(event: RuntimeEvent) -> dict[str, Any] | None:
    if isinstance(event, AgentStartRuntimeEvent):
        return {"type": event.type}
    if isinstance(event, AgentEndRuntimeEvent):
        return {"type": event.type, "messages": serialize_messages(event.messages)}
    if isinstance(event, TurnStartRuntimeEvent):
        return {"type": event.type}
    if isinstance(event, TurnEndRuntimeEvent):
        return _serialize_turn_end_event(event)
    return None


def _wire_from_message_event(event: RuntimeEvent) -> dict[str, Any] | None:
    if isinstance(event, MessageStartRuntimeEvent | MessageEndRuntimeEvent):
        return _serialize_message_payload(event_type=event.type, message=event.message)
    if isinstance(event, MessageUpdateRuntimeEvent):
        return _serialize_message_update_event(event)
    return None


def _wire_from_tool_event(event: RuntimeEvent) -> dict[str, Any] | None:
    if isinstance(event, ToolExecutionStartRuntimeEvent):
        return _serialize_tool_start_event(event)
    if isinstance(event, ToolExecutionUpdateRuntimeEvent):
        return _serialize_tool_update_event(event)
    if isinstance(event, ToolExecutionEndRuntimeEvent):
        return _serialize_tool_end_event(event)
    return None


def runtime_event_to_wire(event: RuntimeEvent) -> dict[str, Any] | None:
    """Convert a runtime event into a JSONL wire event."""
    lifecycle_payload = _wire_from_agent_or_turn_event(event)
    if lifecycle_payload is not None:
        return lifecycle_payload

    message_payload = _wire_from_message_event(event)
    if message_payload is not None:
        return message_payload

    tool_payload = _wire_from_tool_event(event)
    if tool_payload is not None:
        return tool_payload

    if isinstance(event, NoticeRuntimeEvent | CompactionStateChangedRuntimeEvent):
        return None
    raise TypeError(f"Unsupported runtime event: {type(event).__name__}")
