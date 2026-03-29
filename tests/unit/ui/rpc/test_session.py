"""Unit tests for RPC session lifecycle handling."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
from tinyagent.agent_types import AssistantMessage, AssistantMessageEvent, TextContent, UserMessage

from tunacode.types.runtime_events import (
    AgentEndRuntimeEvent,
    AgentStartRuntimeEvent,
    MessageEndRuntimeEvent,
    MessageStartRuntimeEvent,
    MessageUpdateRuntimeEvent,
    TurnEndRuntimeEvent,
    TurnStartRuntimeEvent,
)

from tunacode.core.session import StateManager

from tunacode.ui.rpc.protocol import (
    AbortCommand,
    GetMessagesCommand,
    PromptCommand,
    RpcProtocolError,
    SetModelCommand,
)
from tunacode.ui.rpc.session import RpcSession


class _RecordingTransport:
    def __init__(self) -> None:
        self.writes: list[dict[str, object]] = []
        self.diagnostics: list[str] = []

    async def write(self, payload: dict[str, object]) -> None:
        self.writes.append(payload)

    def write_diagnostic(self, message: str) -> None:
        self.diagnostics.append(message)


async def _wait_until(predicate: Callable[[], bool], *, timeout: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Condition not met before timeout")


def _build_session(
    request_runner: Callable[..., Awaitable[object]],
) -> tuple[RpcSession, StateManager, _RecordingTransport]:
    state_manager = StateManager()
    state_manager.save_session = AsyncMock(return_value=True)  # type: ignore[method-assign]
    transport = _RecordingTransport()
    session = RpcSession(
        state_manager=state_manager,
        transport=transport,  # type: ignore[arg-type]
        request_runner=request_runner,
    )
    return session, state_manager, transport


async def _complete_runner(
    *,
    message: str,
    state_manager: StateManager,
    runtime_event_sink: Callable[[object], Awaitable[None]],
    **_: object,
) -> None:
    user_message = UserMessage(content=[TextContent(text=message)])
    assistant_message = AssistantMessage(
        content=[TextContent(text=f"echo:{message}")],
        stop_reason="complete",
    )

    await runtime_event_sink(AgentStartRuntimeEvent())
    await runtime_event_sink(TurnStartRuntimeEvent())
    await runtime_event_sink(MessageStartRuntimeEvent(message=user_message))
    await runtime_event_sink(MessageEndRuntimeEvent(message=user_message))
    await runtime_event_sink(MessageStartRuntimeEvent(message=assistant_message))
    await runtime_event_sink(
        MessageUpdateRuntimeEvent(
            message=assistant_message,
            assistant_message_event=AssistantMessageEvent(
                type="text_delta", delta=f"echo:{message}"
            ),
        )
    )
    await runtime_event_sink(MessageEndRuntimeEvent(message=assistant_message))
    await runtime_event_sink(TurnEndRuntimeEvent(message=assistant_message, tool_results=[]))
    state_manager.session.conversation.messages.extend([user_message, assistant_message])
    await runtime_event_sink(AgentEndRuntimeEvent(messages=[user_message, assistant_message]))


@pytest.mark.asyncio
async def test_prompt_transitions_idle_to_streaming_to_idle() -> None:
    session, state_manager, transport = _build_session(_complete_runner)

    response = await session.handle_command(
        PromptCommand(request_id="1", command="prompt", prompt="hello")
    )
    await _wait_until(lambda: session._active_request_task is None)  # type: ignore[attr-defined]

    assert response["success"] is True
    assert state_manager.session.conversation.messages
    assert [payload["type"] for payload in transport.writes] == [
        "agent_start",
        "turn_start",
        "message_start",
        "message_end",
        "message_start",
        "message_update",
        "message_end",
        "turn_end",
        "agent_end",
    ]


@pytest.mark.asyncio
async def test_prompt_rejects_second_request_while_streaming() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def _blocking_runner(
        *,
        runtime_event_sink: Callable[[object], Awaitable[None]],
        **_: object,
    ) -> None:
        await runtime_event_sink(AgentStartRuntimeEvent())
        started.set()
        await release.wait()

    session, _state_manager, _transport = _build_session(_blocking_runner)

    await session.handle_command(PromptCommand(request_id="1", command="prompt", prompt="slow"))
    await started.wait()

    with pytest.raises(RpcProtocolError) as excinfo:
        await session.handle_command(
            PromptCommand(request_id="2", command="prompt", prompt="again")
        )

    assert excinfo.value.code == "busy"
    release.set()
    await _wait_until(lambda: session._active_request_task is None)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_abort_cancels_active_request() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _blocking_runner(
        *,
        runtime_event_sink: Callable[[object], Awaitable[None]],
        **_: object,
    ) -> None:
        await runtime_event_sink(AgentStartRuntimeEvent())
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    session, _state_manager, _transport = _build_session(_blocking_runner)

    await session.handle_command(PromptCommand(request_id="1", command="prompt", prompt="slow"))
    await started.wait()
    response = await session.handle_command(AbortCommand(request_id="2", command="abort"))
    await _wait_until(cancelled.is_set)
    await _wait_until(lambda: session._active_request_task is None)  # type: ignore[attr-defined]

    assert response["success"] is True


@pytest.mark.asyncio
async def test_set_model_rejects_while_streaming() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def _blocking_runner(
        *,
        runtime_event_sink: Callable[[object], Awaitable[None]],
        **_: object,
    ) -> None:
        await runtime_event_sink(AgentStartRuntimeEvent())
        started.set()
        await release.wait()

    session, _state_manager, _transport = _build_session(_blocking_runner)

    await session.handle_command(PromptCommand(request_id="1", command="prompt", prompt="slow"))
    await started.wait()

    with pytest.raises(RpcProtocolError) as excinfo:
        await session.handle_command(
            SetModelCommand(request_id="2", command="set_model", model="openai/gpt-4o")
        )

    assert excinfo.value.code == "busy"
    release.set()
    await _wait_until(lambda: session._active_request_task is None)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_get_messages_returns_completed_conversation() -> None:
    session, _state_manager, _transport = _build_session(_complete_runner)

    await session.handle_command(PromptCommand(request_id="1", command="prompt", prompt="hello"))
    await _wait_until(lambda: session._active_request_task is None)  # type: ignore[attr-defined]
    response = await session.handle_command(
        GetMessagesCommand(request_id="2", command="get_messages")
    )

    assert response["success"] is True
    assert response["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "echo:hello"}],
            "stop_reason": "complete",
        },
    ]
