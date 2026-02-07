"""Proxy event handling helpers."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Literal, TypeAlias, TypeGuard, cast

from .agent_types import (
    AssistantContent,
    AssistantMessage,
    AssistantMessageEvent,
    JsonObject,
    JsonValue,
    StopReason,
    TextContent,
    ThinkingContent,
    ToolCallContent,
)


def parse_streaming_json(json_str: str) -> JsonObject | None:
    """Parse partial JSON from a streaming response."""

    def _parse(value: str) -> JsonObject | None:
        try:
            parsed_raw = json.loads(value)
        except json.JSONDecodeError:
            return None
        return cast(JsonObject, parsed_raw) if isinstance(parsed_raw, dict) else None

    parsed = _parse(json_str)
    if parsed is not None:
        return parsed

    fixed = json_str.strip()
    if fixed and not fixed.endswith("}"):
        brace_count = fixed.count("{") - fixed.count("}")
        fixed += "}" * brace_count
    return _parse(fixed)


ProxyEventHandler: TypeAlias = Callable[
    [JsonObject, AssistantMessage], AssistantMessageEvent | None
]


def _get_content_index(proxy_event: JsonObject) -> int:
    value = proxy_event.get("contentIndex")
    return value if isinstance(value, int) else 0


def _ensure_content_slot(partial: AssistantMessage, index: int) -> list[AssistantContent | None]:
    content_list = partial.get("content")
    if content_list is None:
        content_list = []
        partial["content"] = content_list
    while len(content_list) <= index:
        content_list.append(None)
    return cast(list[AssistantContent | None], content_list)


def _get_content(partial: AssistantMessage, index: int) -> AssistantContent | None:
    content_list = partial.get("content", [])
    if index < len(content_list):
        return cast(AssistantContent | None, content_list[index])
    return None


def _is_text_content(content: AssistantContent | None) -> TypeGuard[TextContent]:
    return content is not None and content.get("type") == "text"


def _is_thinking_content(content: AssistantContent | None) -> TypeGuard[ThinkingContent]:
    return content is not None and content.get("type") == "thinking"


def _is_tool_call(content: AssistantContent | None) -> TypeGuard[ToolCallContent]:
    return content is not None and content.get("type") == "tool_call"


_STOP_REASONS: set[StopReason] = {
    "complete",
    "error",
    "aborted",
    "tool_calls",
    "stop",
    "length",
    "tool_use",
}


def _normalize_stop_reason(value: object, default: StopReason) -> StopReason:
    if isinstance(value, str) and value in _STOP_REASONS:
        return cast(StopReason, value)
    return default


def _handle_start_event(
    proxy_event: JsonObject, partial: AssistantMessage
) -> AssistantMessageEvent:
    return {"type": "start", "partial": partial}


def _handle_content_start(
    proxy_event: JsonObject,
    partial: AssistantMessage,
    content_type: Literal["text", "thinking"],
    event_type: Literal["text_start", "thinking_start"],
) -> AssistantMessageEvent:
    content_index = _get_content_index(proxy_event)
    content_list = _ensure_content_slot(partial, content_index)

    if content_type == "text":
        content_list[content_index] = {"type": "text", "text": ""}
    else:
        content_list[content_index] = {"type": "thinking", "thinking": ""}

    return {"type": event_type, "content_index": content_index, "partial": partial}


def _handle_content_delta(
    proxy_event: JsonObject,
    partial: AssistantMessage,
    content_type: Literal["text", "thinking"],
    event_type: Literal["text_delta", "thinking_delta"],
) -> AssistantMessageEvent:
    content_index = _get_content_index(proxy_event)

    delta_val: JsonValue = proxy_event.get("delta", "")
    delta = delta_val if isinstance(delta_val, str) else ""

    content = _get_content(partial, content_index)

    if content_type == "text":
        if not _is_text_content(content):
            raise RuntimeError(f"Received {event_type} for non-text content")
        content["text"] = content.get("text", "") + delta
    else:
        if not _is_thinking_content(content):
            raise RuntimeError(f"Received {event_type} for non-thinking content")
        content["thinking"] = content.get("thinking", "") + delta

    return {
        "type": event_type,
        "content_index": content_index,
        "delta": delta,
        "partial": partial,
    }


def _handle_content_end(
    proxy_event: JsonObject,
    partial: AssistantMessage,
    content_type: Literal["text", "thinking"],
    event_type: Literal["text_end", "thinking_end"],
) -> AssistantMessageEvent:
    content_index = _get_content_index(proxy_event)
    content = _get_content(partial, content_index)

    signature = proxy_event.get("contentSignature")
    signature_str = signature if isinstance(signature, str) else None

    if content_type == "text":
        if not _is_text_content(content):
            raise RuntimeError(f"Received {event_type} for non-text content")
        content["text_signature"] = signature_str
        content_value = content.get("text")
    else:
        if not _is_thinking_content(content):
            raise RuntimeError(f"Received {event_type} for non-thinking content")
        content["thinking_signature"] = signature_str
        content_value = content.get("thinking")

    return {
        "type": event_type,
        "content_index": content_index,
        "content": content_value,
        "partial": partial,
    }


def _handle_text_start(proxy_event: JsonObject, partial: AssistantMessage) -> AssistantMessageEvent:
    return _handle_content_start(proxy_event, partial, "text", "text_start")


def _handle_text_delta(proxy_event: JsonObject, partial: AssistantMessage) -> AssistantMessageEvent:
    return _handle_content_delta(proxy_event, partial, "text", "text_delta")


def _handle_text_end(proxy_event: JsonObject, partial: AssistantMessage) -> AssistantMessageEvent:
    return _handle_content_end(proxy_event, partial, "text", "text_end")


def _handle_thinking_start(
    proxy_event: JsonObject, partial: AssistantMessage
) -> AssistantMessageEvent:
    return _handle_content_start(proxy_event, partial, "thinking", "thinking_start")


def _handle_thinking_delta(
    proxy_event: JsonObject, partial: AssistantMessage
) -> AssistantMessageEvent:
    return _handle_content_delta(proxy_event, partial, "thinking", "thinking_delta")


def _handle_thinking_end(
    proxy_event: JsonObject, partial: AssistantMessage
) -> AssistantMessageEvent:
    return _handle_content_end(proxy_event, partial, "thinking", "thinking_end")


def _handle_toolcall_start(
    proxy_event: JsonObject, partial: AssistantMessage
) -> AssistantMessageEvent:
    content_index = _get_content_index(proxy_event)
    content_list = _ensure_content_slot(partial, content_index)

    tc_id = proxy_event.get("id")
    tc_id_str = tc_id if isinstance(tc_id, str) else ""

    tool_name = proxy_event.get("toolName")
    tool_name_str = tool_name if isinstance(tool_name, str) else ""

    content_list[content_index] = {
        "type": "tool_call",
        "id": tc_id_str,
        "name": tool_name_str,
        "arguments": {},
        "partial_json": "",
    }

    return {"type": "tool_call_start", "content_index": content_index, "partial": partial}


def _handle_toolcall_delta(
    proxy_event: JsonObject, partial: AssistantMessage
) -> AssistantMessageEvent:
    content_index = _get_content_index(proxy_event)

    delta_val: JsonValue = proxy_event.get("delta", "")
    delta = delta_val if isinstance(delta_val, str) else ""

    content = _get_content(partial, content_index)
    if not _is_tool_call(content):
        raise RuntimeError("Received tool_call_delta for non-tool_call content")

    content["partial_json"] = content.get("partial_json", "") + delta
    parsed_args = parse_streaming_json(content["partial_json"])
    content["arguments"] = parsed_args if parsed_args else {}

    content_list = partial.get("content")
    if content_list is None:
        content_list = []
        partial["content"] = content_list
    content_list[content_index] = content

    return {
        "type": "tool_call_delta",
        "content_index": content_index,
        "delta": delta,
        "partial": partial,
    }


def _handle_toolcall_end(
    proxy_event: JsonObject, partial: AssistantMessage
) -> AssistantMessageEvent | None:
    content_index = _get_content_index(proxy_event)
    content = _get_content(partial, content_index)
    if not _is_tool_call(content):
        return None

    content.pop("partial_json", None)
    return {
        "type": "tool_call_end",
        "content_index": content_index,
        "tool_call": content,
        "partial": partial,
    }


def _handle_done_event(proxy_event: JsonObject, partial: AssistantMessage) -> AssistantMessageEvent:
    reason = _normalize_stop_reason(proxy_event.get("reason"), "stop")

    partial["stop_reason"] = reason
    usage = proxy_event.get("usage")
    partial["usage"] = cast(JsonObject, usage) if isinstance(usage, dict) else partial.get("usage")
    return {"type": "done", "reason": reason, "message": partial}


def _handle_error_event(
    proxy_event: JsonObject, partial: AssistantMessage
) -> AssistantMessageEvent:
    reason = _normalize_stop_reason(proxy_event.get("reason"), "error")

    partial["stop_reason"] = reason

    error_message = proxy_event.get("errorMessage")
    partial["error_message"] = error_message if isinstance(error_message, str) else None

    usage = proxy_event.get("usage")
    partial["usage"] = cast(JsonObject, usage) if isinstance(usage, dict) else partial.get("usage")

    return {"type": "error", "reason": reason, "error": partial}


def _handle_unrecognized_event(
    proxy_event: JsonObject, partial: AssistantMessage
) -> AssistantMessageEvent | None:
    event_type = proxy_event.get("type")
    print(f"Warning: Unhandled proxy event type: {event_type}")
    return None


_PROXY_EVENT_HANDLERS: dict[str, ProxyEventHandler] = {
    "start": _handle_start_event,
    "text_start": _handle_text_start,
    "text_delta": _handle_text_delta,
    "text_end": _handle_text_end,
    "thinking_start": _handle_thinking_start,
    "thinking_delta": _handle_thinking_delta,
    "thinking_end": _handle_thinking_end,
    # Proxy protocol uses toolcall_*; we emit tool_call_* to callers.
    "toolcall_start": _handle_toolcall_start,
    "toolcall_delta": _handle_toolcall_delta,
    "toolcall_end": _handle_toolcall_end,
    "done": _handle_done_event,
    "error": _handle_error_event,
}


def process_proxy_event(
    proxy_event: JsonObject, partial: AssistantMessage
) -> AssistantMessageEvent | None:
    event_type = proxy_event.get("type")
    if not isinstance(event_type, str):
        return _handle_unrecognized_event(proxy_event, partial)

    handler = _PROXY_EVENT_HANDLERS.get(event_type)
    if handler:
        return handler(proxy_event, partial)

    return _handle_unrecognized_event(proxy_event, partial)
