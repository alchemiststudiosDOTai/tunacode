"""Characterization tests for streaming helper behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import tunacode.core.agents.agent_components.streaming as streaming_mod
from tunacode.core.agents.agent_components import (
    ToolBuffer,
    flush_buffered_read_only_tools,
    stream_model_request_node,
)
from tunacode.core.state import StateManager


class _FailingStream:
    def __init__(self):
        self._attempts = 0

    async def __aenter__(self):  # pragma: no cover - simple failure helper
        self._attempts += 1
        raise RuntimeError("stream failure")

    async def __aexit__(self, *_) -> None:
        return None


class _MockNode:
    def stream(self, _ctx):
        return _FailingStream()


@pytest.mark.asyncio
async def test_streaming_flushes_buffer_before_retry():
    """Buffered tools flush before streaming retry is attempted."""
    node = _MockNode()
    state_manager = SimpleNamespace()
    state_manager.session = SimpleNamespace(show_thoughts=False)

    tool_buffer = ToolBuffer()
    tool_buffer.add(SimpleNamespace(tool_name="grep"), node)
    tool_callback = AsyncMock()
    streaming_callback = AsyncMock()
    flush_coordinator = SimpleNamespace(
        ensure_before_request=AsyncMock(),
        flush=AsyncMock(),
    )

    streaming_mod.STREAMING_AVAILABLE = True

    await stream_model_request_node(
        node,
        agent_run_ctx=object(),
        state_manager=state_manager,
        streaming_callback=streaming_callback,
        request_id="req",
        iteration_index=1,
        tool_buffer=tool_buffer,
        tool_callback=tool_callback,
        flush_coordinator=flush_coordinator,
    )

    assert flush_coordinator.ensure_before_request.await_count == 2
    flush_coordinator.ensure_before_request.assert_any_await("pre-request:streaming")
    assert flush_coordinator.flush.await_count >= 1
    flush_call = flush_coordinator.flush.await_args_list[0]
    assert flush_call.kwargs.get("origin") == "stream-retry"


@pytest.mark.asyncio
async def test_flush_buffer_adds_tool_return_messages() -> None:
    """Buffered read-only tools produce synthetic tool returns when flushed."""
    state_manager = StateManager()
    tool_buffer = ToolBuffer()
    node = SimpleNamespace()
    tool_call_id = "call-123"
    part = SimpleNamespace(
        tool_name="grep",
        args={"pattern": "TODO"},
        tool_call_id=tool_call_id,
        part_kind="tool-call",
    )
    tool_buffer.add(part, node)

    state_manager.session.messages.append(
        SimpleNamespace(
            parts=[
                SimpleNamespace(
                    tool_name="grep",
                    args={"pattern": "TODO"},
                    tool_call_id=tool_call_id,
                    part_kind="tool-call",
                )
            ],
            kind="request",
        )
    )

    async def tool_callback(mock_part: SimpleNamespace, _node: object) -> str:  # type: ignore[unused-argument]
        return "matched"

    executed = await flush_buffered_read_only_tools(
        tool_buffer,
        tool_callback,
        state_manager,
        origin="test",
    )

    assert executed is True

    tool_returns = [
        message_part
        for message in state_manager.session.messages
        for message_part in getattr(message, "parts", [])
        if getattr(message_part, "part_kind", "") == "tool-return"
    ]

    assert any(ret.tool_call_id == tool_call_id for ret in tool_returns)
