"""Unit tests for runtime-event to wire-event mapping."""

from __future__ import annotations

from tinyagent.agent_types import AssistantMessage, AssistantMessageEvent, TextContent

from tunacode.types.runtime_events import MessageUpdateRuntimeEvent, ToolExecutionEndRuntimeEvent

from tunacode.ui.rpc.adapter import runtime_event_to_wire


def test_runtime_message_update_maps_to_wire_payload() -> None:
    message = AssistantMessage(content=[TextContent(text="hello")], stop_reason="complete")
    event = MessageUpdateRuntimeEvent(
        message=message,
        assistant_message_event=AssistantMessageEvent(type="text_delta", delta="hello"),
    )

    payload = runtime_event_to_wire(event)

    assert payload == {
        "type": "message_update",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "hello"}],
            "stop_reason": "complete",
        },
        "assistantMessageEvent": {
            "type": "text_delta",
            "delta": "hello",
        },
    }


def test_runtime_tool_end_maps_correlation_fields() -> None:
    payload = runtime_event_to_wire(
        ToolExecutionEndRuntimeEvent(
            tool_call_id="call_1",
            tool_name="bash",
            args={"command": "pwd"},
            is_error=False,
            duration_ms=12.5,
        )
    )

    assert payload == {
        "type": "tool_execution_end",
        "toolCallId": "call_1",
        "toolName": "bash",
        "args": {"command": "pwd"},
        "isError": False,
        "durationMs": 12.5,
    }
