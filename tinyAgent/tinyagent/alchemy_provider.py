"""Alchemy (Rust) provider for tinyagent.

This provider uses the Rust crate `alchemy-llm` via a small PyO3 binding
(`bindings/alchemy_llm_py`).

Important limitations:
- Only OpenAI-compatible `/chat/completions` streaming is supported.
- Image blocks are not supported yet.
- Python receives events by calling a blocking `next_event()` method in a thread,
  so it is real-time but has more overhead than a native async generator.

Build/install the binding first (from repo root):

    python -m pip install maturin
    cd bindings/alchemy_llm_py
    maturin develop

"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from .agent_types import (
    AgentTool,
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    Model,
    SimpleStreamOptions,
)


@dataclass
class OpenAICompatModel(Model):
    """Model config for OpenAI-compatible chat/completions endpoints."""

    # tinyagent's Model fields
    provider: str = "openrouter"
    id: str = "moonshotai/kimi-k2.5"
    api: str = "openai-completions"

    # additional fields used by the Rust binding
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    name: str | None = None
    headers: dict[str, str] | None = None

    # optional hints (not currently used by tinyagent itself)
    context_window: int = 128_000
    max_tokens: int = 4096
    reasoning: bool = False


@dataclass
class AlchemyStreamResponse:
    """StreamResponse backed by a Rust stream handle."""

    _handle: Any
    _final_message: AssistantMessage | None = None

    async def result(self) -> AssistantMessage:
        if self._final_message is None:
            msg = await asyncio.to_thread(self._handle.result)
            if not isinstance(msg, dict):
                raise RuntimeError("alchemy_llm_py returned an invalid final message")
            self._final_message = msg  # type: ignore[assignment]
        return self._final_message

    def __aiter__(self):
        return self

    async def __anext__(self) -> AssistantMessageEvent:
        ev = await asyncio.to_thread(self._handle.next_event)
        if ev is None:
            raise StopAsyncIteration
        if not isinstance(ev, dict):
            raise RuntimeError("alchemy_llm_py returned an invalid event")
        return ev  # type: ignore[return-value]


def _convert_tools(tools: list[AgentTool] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    out: list[dict[str, Any]] = []
    for t in tools:
        out.append(
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters or {"type": "object", "properties": {}},
            }
        )
    return out


async def stream_alchemy_openai_completions(
    model: Model,
    context: Context,
    options: SimpleStreamOptions,
) -> AlchemyStreamResponse:
    """Stream using the Rust alchemy-llm implementation (OpenAI-compatible)."""

    try:
        import alchemy_llm_py  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "alchemy_llm_py is not installed. "
            "Build it via `maturin develop` in bindings/alchemy_llm_py"
        ) from e

    base_url = getattr(model, "base_url", None)
    if not isinstance(base_url, str) or not base_url:
        raise ValueError("Model must have a non-empty `base_url` attribute")

    model_dict: dict[str, Any] = {
        "id": model.id,
        "provider": model.provider,
        "base_url": base_url,
        "name": getattr(model, "name", None),
        "headers": getattr(model, "headers", None),
        "reasoning": getattr(model, "reasoning", False),
        "context_window": getattr(model, "context_window", None),
        "max_tokens": getattr(model, "max_tokens", None),
    }

    context_dict: dict[str, Any] = {
        "system_prompt": context.system_prompt or "",
        "messages": context.messages,
        "tools": _convert_tools(context.tools),
    }

    options_dict: dict[str, Any] = {
        "api_key": options.get("api_key"),
        "temperature": options.get("temperature"),
        "max_tokens": options.get("max_tokens"),
    }

    # Start Rust streaming in-process.
    # The returned handle exposes blocking `next_event()` / `result()`.
    handle = alchemy_llm_py.openai_completions_stream(
        model_dict,
        context_dict,
        options_dict,
    )

    return AlchemyStreamResponse(_handle=handle)
