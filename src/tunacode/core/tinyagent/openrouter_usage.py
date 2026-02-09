"""OpenRouter streaming wrapper that captures token usage (temporary shim).

Why this exists
---------------
TunaCode renders agent throughput (t/s) using ``session.usage.last_call_usage``.
During the pydantic-ai -> tinyagent migration, the write-side population of token
usage was dropped.

At the moment, tinyagent's upstream OpenRouter streaming provider does not
extract ``usage`` from the OpenRouter SSE stream and does not attach it to the
final assistant message.

What this shim does
-------------------
- Parses OpenRouter SSE chunks and captures any top-level ``{"usage": {...}}``
  payload (typically present on the final chunk).
- Attaches that dict onto the final assistant message as ``message["usage"]``.

Non-goals
---------
- We do *not* attempt to compute tokens ourselves.
- We keep the rest of the provider behavior identical to tinyagent.

Maintenance note
----------------
This wrapper intentionally imports a few helper functions from
``tinyagent.openrouter_provider`` (some are underscore-prefixed / private API).
This is acceptable for now because TunaCode pins ``tiny-agent-os``.

TODO(core): delete this file once tinyagent/OpenRouter provider emits usage on the
assistant message or provides a stable usage callback.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

import httpx
from tinyagent.agent_types import Context, Model, SimpleStreamOptions
from tinyagent.openrouter_provider import (  # type: ignore
    OPENROUTER_API_URL,
    OpenRouterStreamResponse,
    _build_request_body,
    _convert_messages_to_openai_format,
    _convert_tools_to_openai_format,
    _finalize_tool_calls,
    _handle_text_delta,
    _handle_tool_call_delta,
)


@dataclass(frozen=True, slots=True)
class _OpenRouterSseEvent:
    done: bool
    delta: dict[str, object] | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None


def _extract_sse_data(line: str) -> str | None:
    if not line.startswith("data: "):
        return None
    return line[6:].strip()


def _parse_openrouter_sse_line(line: str) -> _OpenRouterSseEvent | None:
    data = _extract_sse_data(line)
    if data is None:
        return None

    if data == "[DONE]":
        return _OpenRouterSseEvent(done=True)

    try:
        chunk_raw = json.loads(data)
    except json.JSONDecodeError:
        return None

    if not isinstance(chunk_raw, dict):
        return None

    usage_raw = chunk_raw.get("usage")
    usage = usage_raw if isinstance(usage_raw, dict) else None

    choices = chunk_raw.get("choices")
    if not isinstance(choices, list) or not choices:
        # Some providers might send usage-only chunks; keep them.
        if usage is not None:
            return _OpenRouterSseEvent(done=False, delta=None, finish_reason=None, usage=usage)
        return None

    choice0 = choices[0]
    if not isinstance(choice0, dict):
        return None

    delta_raw = choice0.get("delta")
    delta = delta_raw if isinstance(delta_raw, dict) else {}

    finish_raw = choice0.get("finish_reason")
    finish_reason = finish_raw if isinstance(finish_raw, str) and finish_raw else None

    return _OpenRouterSseEvent(
        done=False,
        delta=delta,
        finish_reason=finish_reason,
        usage=usage,
    )


async def stream_openrouter_with_usage(
    model: Model,
    context: Context,
    options: SimpleStreamOptions,
) -> OpenRouterStreamResponse:
    """Stream a response from OpenRouter and attach token usage to the message."""

    api_key = options.get("api_key") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OpenRouter API key required")

    messages = _convert_messages_to_openai_format(context.messages)
    if context.system_prompt:
        messages.insert(0, {"role": "system", "content": context.system_prompt})

    tools = _convert_tools_to_openai_format(context.tools)
    request_body = _build_request_body(model.id, messages, tools, options)

    response = OpenRouterStreamResponse()
    partial: dict[str, Any] = {
        "role": "assistant",
        "content": [],
        "stop_reason": None,
        "timestamp": int(asyncio.get_event_loop().time() * 1000),
    }

    current_text = ""
    tool_calls_map: dict[int, dict[str, str]] = {}
    last_usage: dict[str, Any] | None = None

    async with (
        httpx.AsyncClient() as client,
        client.stream(
            "POST",
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=None,
        ) as http_response,
    ):
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

            if parsed.usage is not None:
                last_usage = parsed.usage

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

    if last_usage is not None:
        partial["usage"] = last_usage

    response._final_message = partial  # type: ignore[attr-defined]
    response._events.append({"type": "done", "partial": partial})

    return response
