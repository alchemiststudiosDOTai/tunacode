"""Proxy stream function for apps that route LLM calls through a server.

The server manages auth and proxies requests to LLM providers.

This module implements a `StreamFn` compatible with the agent loop.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Literal, cast

import httpx

from .agent_types import (
    AgentTool,
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    JsonObject,
    JsonValue,
    Model,
    StreamResponse,
)
from .proxy_event_handlers import process_proxy_event


@dataclass
class ProxyStreamOptions:
    """Options for proxy streaming."""

    auth_token: str
    proxy_url: str
    temperature: float | None = None
    max_tokens: int | None = None
    reasoning: JsonValue | None = None
    signal: Callable[[], bool] | None = None  # cancellation check function


def _create_initial_partial(model: Model) -> AssistantMessage:
    """Create the initial partial message for streaming."""

    return {
        "role": "assistant",
        "stop_reason": "stop",
        "content": [],
        "api": model.api,
        "provider": model.provider,
        "model": model.id,
        "usage": None,
        "timestamp": int(time.time() * 1000),
    }


def _tool_to_json(tool: AgentTool) -> JsonObject:
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
        "label": tool.label,
    }


def _tools_to_json(tools: list[AgentTool] | None) -> list[JsonObject] | None:
    if not tools:
        return None
    return [_tool_to_json(tool) for tool in tools]


def _model_to_json(model: Model) -> JsonObject:
    return {
        "provider": model.provider,
        "id": model.id,
        "api": model.api,
        "thinking_level": model.thinking_level,
    }


def _context_to_json(context: Context) -> JsonObject:
    result: JsonObject = {
        "system_prompt": context.system_prompt,
        "messages": cast(JsonValue, context.messages),
    }

    tools_json = _tools_to_json(context.tools)
    if tools_json is not None:
        result["tools"] = cast(JsonValue, tools_json)

    return result


def _build_proxy_request_body(
    model: Model, context: Context, options: ProxyStreamOptions
) -> JsonObject:
    """Build the request body for the proxy."""

    return {
        "model": _model_to_json(model),
        "context": _context_to_json(context),
        "options": {
            "temperature": options.temperature,
            # Proxy API uses maxTokens (camelCase) on the wire.
            "maxTokens": options.max_tokens,
            "reasoning": options.reasoning,
        },
    }


async def _parse_error_response(response: httpx.Response) -> str:
    """Parse error message from a non-200 proxy response."""

    error_message = f"Proxy error: {response.status_code}"
    try:
        error_data = await response.aread()
        error_json = json.loads(error_data)
        if isinstance(error_json, dict) and error_json.get("error"):
            error_message = f"Proxy error: {error_json['error']}"
    except Exception:
        pass
    return error_message


def _parse_sse_lines(buffer: str, chunk: str) -> tuple[str, list[str]]:
    buffer += chunk
    lines = buffer.split("\n")
    remaining = lines.pop() if lines else ""
    return remaining, lines


def _parse_sse_data(line: str) -> JsonObject | None:
    if not line.startswith("data: "):
        return None

    data = line[6:].strip()
    if not data:
        return None

    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        return None

    return cast(JsonObject, parsed) if isinstance(parsed, dict) else None


async def _iter_sse_events(response: httpx.Response) -> AsyncIterator[JsonObject]:
    """Yield parsed SSE events from an httpx streaming response."""

    buffer = ""
    async for chunk in response.aiter_text():
        buffer, lines = _parse_sse_lines(buffer, chunk)
        for line in lines:
            data = _parse_sse_data(line)
            if data is not None:
                yield data


class ProxyStreamResponse(StreamResponse):
    """A streaming response that reads SSE from a proxy server."""

    def __init__(self, *, model: Model, context: Context, options: ProxyStreamOptions):
        self._model = model
        self._context = context
        self._options = options

        self._partial: AssistantMessage = _create_initial_partial(model)
        self._final: AssistantMessage | None = None

        self._queue: asyncio.Queue[AssistantMessageEvent | None] = asyncio.Queue()
        self._task = asyncio.create_task(self._run())

    def __aiter__(self):
        return self

    async def __anext__(self) -> AssistantMessageEvent:
        event = await self._queue.get()
        if event is None:
            raise StopAsyncIteration
        return event

    async def result(self) -> AssistantMessage:
        await self._task
        if self._final is None:
            raise RuntimeError("No final message available")
        return self._final

    def _is_aborted(self) -> bool:
        return self._options.signal() if self._options.signal else False

    def _set_final_from_event(self, event: AssistantMessageEvent) -> None:
        message = event.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant":
            self._final = message
        else:
            self._final = self._partial

    async def _queue_event(self, event: AssistantMessageEvent) -> None:
        if event.get("type") in {"done", "error"}:
            self._set_final_from_event(event)
        await self._queue.put(event)

    async def _stream_from_http_response(self, response: httpx.Response) -> None:
        async for proxy_event in _iter_sse_events(response):
            if self._is_aborted():
                raise RuntimeError("Request aborted by user")

            event = process_proxy_event(proxy_event, self._partial)
            if event is None:
                continue
            await self._queue_event(event)

    async def _run_success(self) -> None:
        if self._is_aborted():
            raise RuntimeError("Request aborted by user")

        request_body = _build_proxy_request_body(self._model, self._context, self._options)

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self._options.proxy_url}/api/stream",
                headers={
                    "Authorization": f"Bearer {self._options.auth_token}",
                    "Content-Type": "application/json",
                },
                json=request_body,
                timeout=None,
            ) as response:
                if response.status_code != 200:
                    raise RuntimeError(await _parse_error_response(response))

                await self._stream_from_http_response(response)

        if self._final is None:
            self._final = self._partial
            await self._queue_event({"type": "done", "partial": self._partial})

    async def _run_error(self, exc: Exception) -> None:
        reason: Literal["aborted", "error"] = "aborted" if self._is_aborted() else "error"
        self._partial["stop_reason"] = reason
        self._partial["error_message"] = str(exc)
        self._final = self._partial
        await self._queue_event({"type": "error", "reason": reason, "error": self._partial})

    async def _run(self) -> None:
        try:
            await self._run_success()
        except Exception as exc:  # noqa: BLE001
            await self._run_error(exc)
        finally:
            await self._queue.put(None)


async def stream_proxy(
    model: Model, context: Context, options: ProxyStreamOptions
) -> ProxyStreamResponse:
    """Stream function compatible with the agent loop."""

    return ProxyStreamResponse(model=model, context=context, options=options)


async def create_proxy_stream(
    model: Model,
    context: Context,
    auth_token: str,
    proxy_url: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    reasoning: JsonValue | None = None,
    signal: Callable[[], bool] | None = None,
) -> ProxyStreamResponse:
    """Convenience helper to create a proxy stream."""

    options = ProxyStreamOptions(
        auth_token=auth_token,
        proxy_url=proxy_url,
        temperature=temperature,
        max_tokens=max_tokens,
        reasoning=reasoning,
        signal=signal,
    )
    return await stream_proxy(model, context, options)


__all__ = [
    "ProxyStreamOptions",
    "ProxyStreamResponse",
    "stream_proxy",
    "create_proxy_stream",
]
