"""Tests for thinking/text delta routing in RequestOrchestrator."""

from __future__ import annotations

from types import SimpleNamespace

from tunacode.core.agents.main import RequestOrchestrator
from tunacode.core.session import StateManager


def _build_orchestrator(
    *,
    streaming_chunks: list[str] | None,
    thinking_chunks: list[str] | None,
) -> tuple[RequestOrchestrator, StateManager]:
    state_manager = StateManager()

    async def _streaming_callback(chunk: str) -> None:
        if streaming_chunks is not None:
            streaming_chunks.append(chunk)

    async def _thinking_callback(chunk: str) -> None:
        if thinking_chunks is not None:
            thinking_chunks.append(chunk)

    orchestrator = RequestOrchestrator(
        message="test",
        model="openai/gpt-4o",
        state_manager=state_manager,
        tool_callback=None,
        streaming_callback=_streaming_callback if streaming_chunks is not None else None,
        thinking_callback=_thinking_callback if thinking_chunks is not None else None,
    )
    return orchestrator, state_manager


async def test_text_delta_routes_to_streaming_and_updates_debug_accumulator() -> None:
    streamed: list[str] = []
    thought_chunks: list[str] = []
    orchestrator, state_manager = _build_orchestrator(
        streaming_chunks=streamed,
        thinking_chunks=thought_chunks,
    )

    event = SimpleNamespace(assistant_message_event={"type": "text_delta", "delta": "hello"})
    await orchestrator._handle_message_update(event)

    assert streamed == ["hello"]
    assert thought_chunks == []
    assert state_manager.session._debug_raw_stream_accum == "hello"


async def test_thinking_delta_routes_without_streaming_callback() -> None:
    thought_chunks: list[str] = []
    orchestrator, state_manager = _build_orchestrator(
        streaming_chunks=None,
        thinking_chunks=thought_chunks,
    )

    event = SimpleNamespace(
        assistant_message_event={"type": "thinking_delta", "delta": "reasoning"}
    )
    await orchestrator._handle_message_update(event)

    assert thought_chunks == ["reasoning"]
    assert state_manager.session._debug_raw_stream_accum == ""


async def test_non_delta_or_invalid_events_are_ignored() -> None:
    streamed: list[str] = []
    thought_chunks: list[str] = []
    orchestrator, state_manager = _build_orchestrator(
        streaming_chunks=streamed,
        thinking_chunks=thought_chunks,
    )

    invalid_events = [
        SimpleNamespace(assistant_message_event=None),
        SimpleNamespace(assistant_message_event={"type": "text_delta", "delta": ""}),
        SimpleNamespace(assistant_message_event={"type": "thinking_delta", "delta": 123}),
        SimpleNamespace(assistant_message_event={"type": "message_end", "delta": "ignored"}),
    ]

    for event in invalid_events:
        await orchestrator._handle_message_update(event)

    assert streamed == []
    assert thought_chunks == []
    assert state_manager.session._debug_raw_stream_accum == ""
