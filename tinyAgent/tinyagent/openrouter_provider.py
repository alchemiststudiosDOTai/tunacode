"""OpenRouter provider for the agent framework.

Implements streaming LLM calls via the OpenRouter API.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import TypeGuard, cast

import httpx

from .agent_types import (
    AgentTool,
    AssistantContent,
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    JsonObject,
    Message,
    Model,
    SimpleStreamOptions,
    TextContent,
    ToolCallContent,
    ToolResultMessage,
    UserMessage,
)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass
class OpenRouterModel(Model):
    """OpenRouter model configuration."""

    provider: str = "openrouter"
    id: str = "anthropic/claude-3.5-sonnet"
    api: str = "openrouter"


def _convert_tools_to_openai_format(
    tools: list[AgentTool] | None,
) -> list[dict[str, object]] | None:
    if not tools:
        return None

    result: list[dict[str, object]] = []
    for tool in tools:
        result.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters or {"type": "object", "properties": {}},
                },
            }
        )
    return result


def _is_text_content(content: AssistantContent | None) -> TypeGuard[TextContent]:
    return content is not None and content.get("type") == "text"


def _extract_text_parts(blocks: list[TextContent | dict[str, object]]) -> list[str]:
    text_parts: list[str] = []
    for part in blocks:
        if isinstance(part, dict) and part.get("type") == "text":
            value = part.get("text")
            if isinstance(value, str):
                text_parts.append(value)
    return text_parts


def _convert_user_message(msg: UserMessage) -> dict[str, object]:
    content = msg.get("content", [])
    text_parts = _extract_text_parts(cast(list[TextContent | dict[str, object]], content))
    return {"role": "user", "content": "\n".join(text_parts)}


def _convert_assistant_message(msg: AssistantMessage) -> dict[str, object]:
    content = msg.get("content", [])
    text_parts: list[str] = []
    tool_calls: list[dict[str, object]] = []

    for part in content:
        if not part:
            continue

        ptype = part.get("type")
        if ptype == "text":
            text_val = part.get("text")
            if isinstance(text_val, str):
                text_parts.append(text_val)
        elif ptype == "tool_call":
            tc_args: JsonObject = cast(JsonObject, part.get("arguments", {}))
            tool_calls.append(
                {
                    "id": part.get("id"),
                    "type": "function",
                    "function": {
                        "name": part.get("name"),
                        "arguments": json.dumps(tc_args),
                    },
                }
            )

    msg_dict: dict[str, object] = {"role": "assistant"}
    if text_parts:
        msg_dict["content"] = "\n".join(text_parts)
    if tool_calls:
        msg_dict["tool_calls"] = tool_calls
    return msg_dict


def _convert_tool_result_message(msg: ToolResultMessage) -> dict[str, object]:
    tool_call_id = msg.get("tool_call_id")
    content = msg.get("content", [])
    text_parts = _extract_text_parts(cast(list[TextContent | dict[str, object]], content))
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": "\n".join(text_parts),
    }


def _convert_messages_to_openai_format(messages: list[Message]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []

    for msg in messages:
        role = msg.get("role")
        if role == "user":
            result.append(_convert_user_message(cast(UserMessage, msg)))
        elif role == "assistant":
            result.append(_convert_assistant_message(cast(AssistantMessage, msg)))
        elif role == "tool_result":
            result.append(_convert_tool_result_message(cast(ToolResultMessage, msg)))

    return result


@dataclass
class OpenRouterStreamResponse:
    """Streaming response from OpenRouter."""

    _final_message: AssistantMessage | None = None
    _events: list[AssistantMessageEvent] = field(default_factory=list)
    _index: int = 0

    async def result(self) -> AssistantMessage:
        if self._final_message is None:
            raise RuntimeError("No final message available")
        return self._final_message

    def __aiter__(self):
        return self

    async def __anext__(self) -> AssistantMessageEvent:
        if self._index >= len(self._events):
            raise StopAsyncIteration
        event = self._events[self._index]
        self._index += 1
        return event


def _build_request_body(
    model_id: str,
    messages: list[dict[str, object]],
    tools: list[dict[str, object]] | None,
    options: SimpleStreamOptions,
) -> dict[str, object]:
    request_body: dict[str, object] = {
        "model": model_id,
        "messages": messages,
        "stream": True,
    }

    if tools:
        request_body["tools"] = tools

    temperature = options.get("temperature")
    if temperature is not None:
        request_body["temperature"] = temperature

    max_tokens = options.get("max_tokens")
    if max_tokens:
        request_body["max_tokens"] = max_tokens

    return request_body


def _handle_text_delta(
    delta: dict[str, object],
    current_text: str,
    partial: AssistantMessage,
    response: OpenRouterStreamResponse,
) -> str:
    content = delta.get("content")
    if not isinstance(content, str) or not content:
        return current_text

    current_text += content

    content_list = partial.get("content")
    if content_list is None:
        content_list = []
        partial["content"] = content_list

    last_content = content_list[-1] if content_list else None
    if not _is_text_content(last_content):
        content_list.append({"type": "text", "text": current_text})
    else:
        last_content["text"] = current_text

    response._events.append({"type": "text_delta", "partial": partial, "delta": content})
    return current_text


def _handle_tool_call_delta(
    delta: dict[str, object],
    tool_calls_map: dict[int, dict[str, str]],
    partial: AssistantMessage,
    response: OpenRouterStreamResponse,
) -> None:
    tool_calls = delta.get("tool_calls")
    if not isinstance(tool_calls, list):
        return

    for tc_raw in tool_calls:
        if not isinstance(tc_raw, dict):
            continue

        idx = tc_raw.get("index")
        idx_int = idx if isinstance(idx, int) else 0

        if idx_int not in tool_calls_map:
            tool_calls_map[idx_int] = {"id": "", "name": "", "arguments": ""}

        tc_id = tc_raw.get("id")
        if isinstance(tc_id, str) and tc_id:
            tool_calls_map[idx_int]["id"] = tc_id

        func = tc_raw.get("function")
        if isinstance(func, dict):
            name = func.get("name")
            if isinstance(name, str) and name:
                tool_calls_map[idx_int]["name"] = name
            args = func.get("arguments")
            if isinstance(args, str) and args:
                tool_calls_map[idx_int]["arguments"] += args

        response._events.append({"type": "tool_call_delta", "partial": partial})


def _finalize_tool_calls(
    tool_calls_map: dict[int, dict[str, str]], partial: AssistantMessage
) -> None:
    content_list = partial.get("content")
    if content_list is None:
        content_list = []
        partial["content"] = content_list

    for idx in sorted(tool_calls_map.keys()):
        tc = tool_calls_map[idx]

        args: JsonObject
        try:
            parsed = json.loads(tc["arguments"]) if tc["arguments"] else {}
            args = cast(JsonObject, parsed) if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            args = {}

        content_list.append(
            cast(
                ToolCallContent,
                {
                    "type": "tool_call",
                    "id": tc["id"],
                    "name": tc["name"],
                    "arguments": args,
                },
            )
        )


@dataclass(frozen=True)
class _OpenRouterSseEvent:
    done: bool
    delta: dict[str, object] | None = None
    finish_reason: str | None = None


def _extract_sse_data(line: str) -> str | None:
    if not line.startswith("data: "):
        return None
    return line[6:].strip()


def _parse_openrouter_chunk(data: str) -> tuple[dict[str, object], str | None] | None:
    try:
        chunk_raw = json.loads(data)
    except json.JSONDecodeError:
        return None

    if not isinstance(chunk_raw, dict):
        return None

    choices = chunk_raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    choice0 = choices[0]
    if not isinstance(choice0, dict):
        return None

    delta_raw = choice0.get("delta")
    delta = cast(dict[str, object], delta_raw) if isinstance(delta_raw, dict) else {}

    finish_raw = choice0.get("finish_reason")
    finish_reason = finish_raw if isinstance(finish_raw, str) and finish_raw else None

    return delta, finish_reason


def _parse_openrouter_sse_line(line: str) -> _OpenRouterSseEvent | None:
    data = _extract_sse_data(line)
    if data is None:
        return None

    if data == "[DONE]":
        return _OpenRouterSseEvent(done=True)

    parsed = _parse_openrouter_chunk(data)
    if parsed is None:
        return None

    delta, finish_reason = parsed
    return _OpenRouterSseEvent(done=False, delta=delta, finish_reason=finish_reason)


async def stream_openrouter(
    model: Model,
    context: Context,
    options: SimpleStreamOptions,
) -> OpenRouterStreamResponse:
    """Stream a response from OpenRouter."""

    api_key = options.get("api_key") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OpenRouter API key required")

    messages = _convert_messages_to_openai_format(context.messages)
    if context.system_prompt:
        messages.insert(0, {"role": "system", "content": context.system_prompt})

    tools = _convert_tools_to_openai_format(context.tools)
    request_body = _build_request_body(model.id, messages, tools, options)

    response = OpenRouterStreamResponse()
    partial: AssistantMessage = {
        "role": "assistant",
        "content": [],
        "stop_reason": None,
        "timestamp": int(asyncio.get_event_loop().time() * 1000),
    }

    current_text = ""
    tool_calls_map: dict[int, dict[str, str]] = {}

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=None,
        ) as http_response:
            if http_response.status_code != 200:
                error_data = await http_response.aread()
                raise RuntimeError(
                    f"OpenRouter error {http_response.status_code}: {error_data.decode()}"
                )

            response._events.append({"type": "start", "partial": partial})

            async for line in http_response.aiter_lines():
                parsed = _parse_openrouter_sse_line(line)
                if parsed is None:
                    continue
                if parsed.done:
                    break

                delta = parsed.delta or {}
                current_text = _handle_text_delta(delta, current_text, partial, response)
                _handle_tool_call_delta(delta, tool_calls_map, partial, response)

                if parsed.finish_reason:
                    partial["stop_reason"] = (
                        "tool_calls" if parsed.finish_reason == "tool_calls" else "complete"
                    )

    _finalize_tool_calls(tool_calls_map, partial)
    response._final_message = partial
    response._events.append({"type": "done", "partial": partial})

    return response
