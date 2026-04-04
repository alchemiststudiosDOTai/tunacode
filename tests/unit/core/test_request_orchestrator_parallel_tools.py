"""RequestOrchestrator tool lifecycle tests for parallel tinyagent batches."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from tinyagent.agent_types import (
    AgentToolResult,
    AssistantMessage,
    TextContent,
    ToolCallContent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    UserMessage,
)

from tunacode.types.canonical import ToolCallStatus
from tunacode.utils.messaging import estimate_messages_tokens

from tunacode.core.agents import main as agent_main
from tunacode.core.agents.main import RequestOrchestrator, _TinyAgentStreamState
from tunacode.core.logging.manager import get_logger
from tunacode.core.session import StateManager


def _build_orchestrator_harness(
    *,
    start_events: list[str] | None = None,
    result_events: list[tuple[str, str, dict[str, object], AgentToolResult | None, float | None]]
    | None = None,
) -> tuple[RequestOrchestrator, _TinyAgentStreamState, StateManager]:
    state_manager = StateManager()

    def _on_tool_start(tool_name: str) -> None:
        if start_events is not None:
            start_events.append(tool_name)

    def _on_tool_result(
        tool_name: str,
        status: str,
        args: dict[str, object],
        result: AgentToolResult | None,
        duration_ms: float | None,
    ) -> None:
        if result_events is not None:
            result_events.append((tool_name, status, args, result, duration_ms))

    orchestrator = RequestOrchestrator(
        message="test",
        model="openai/gpt-4o",
        state_manager=state_manager,
        streaming_callback=None,
        tool_result_callback=_on_tool_result if result_events is not None else None,
        tool_start_callback=_on_tool_start if start_events is not None else None,
    )
    state = _TinyAgentStreamState(
        runtime=state_manager.session.runtime,
        tool_start_times={},
        active_tool_call_ids=set(),
        batch_tool_call_ids=set(),
    )
    return orchestrator, state, state_manager


@pytest.mark.asyncio
async def test_tool_handlers_preserve_registry_and_callbacks_for_parallel_batch() -> None:
    start_events: list[str] = []
    result_events: list[
        tuple[str, str, dict[str, object], AgentToolResult | None, float | None]
    ] = []
    orchestrator, state, state_manager = _build_orchestrator_harness(
        start_events=start_events,
        result_events=result_events,
    )

    await orchestrator._handle_stream_tool_execution_start(
        ToolExecutionStartEvent(
            tool_call_id="tool-a",
            tool_name="read_file",
            args={"filepath": "a.py"},
        ),
        agent=object(),
        state=state,
        baseline_message_count=0,
    )
    await orchestrator._handle_stream_tool_execution_start(
        ToolExecutionStartEvent(
            tool_call_id="tool-b",
            tool_name="discover",
            args={"query": "TODO"},
        ),
        agent=object(),
        state=state,
        baseline_message_count=0,
    )

    assert start_events == ["read_file", "discover"]
    assert state_manager.session.runtime.tool_registry.get_args("tool-a") == {"filepath": "a.py"}
    assert state_manager.session.runtime.tool_registry.get_args("tool-b") == {"query": "TODO"}

    await orchestrator._handle_stream_tool_execution_end(
        ToolExecutionEndEvent(
            tool_call_id="tool-a",
            tool_name="read_file",
            is_error=False,
            result=AgentToolResult(content=[TextContent(text="read complete")], details={}),
        ),
        agent=object(),
        state=state,
        baseline_message_count=0,
    )
    await orchestrator._handle_stream_tool_execution_end(
        ToolExecutionEndEvent(
            tool_call_id="tool-b",
            tool_name="discover",
            is_error=False,
            result=AgentToolResult(content=[TextContent(text="found")], details={}),
        ),
        agent=object(),
        state=state,
        baseline_message_count=0,
    )

    assert [(name, status) for name, status, *_ in result_events] == [
        ("read_file", "completed"),
        ("discover", "completed"),
    ]
    assert all(duration_ms is None for *_, duration_ms in result_events)
    assert result_events[0][3] is not None
    assert result_events[0][3].content[0].text == "read complete"  # type: ignore[union-attr]

    registry = state_manager.session.runtime.tool_registry
    tool_a = registry.get("tool-a")
    tool_b = registry.get("tool-b")
    assert tool_a is not None
    assert tool_b is not None
    assert tool_a.status is ToolCallStatus.COMPLETED
    assert tool_b.status is ToolCallStatus.COMPLETED
    assert tool_a.result is not None
    assert tool_a.result.get_text_content() == "read complete"
    assert tool_b.result is not None
    assert tool_b.result.get_text_content() == "found"


@pytest.mark.asyncio
async def test_single_tool_duration_is_reported_when_not_in_parallel_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result_events: list[
        tuple[str, str, dict[str, object], AgentToolResult | None, float | None]
    ] = []
    orchestrator, state, _state_manager = _build_orchestrator_harness(
        start_events=[],
        result_events=result_events,
    )

    perf_counter_values = iter([100.0, 100.5])
    monkeypatch.setattr(agent_main.time, "perf_counter", lambda: next(perf_counter_values))

    await orchestrator._handle_stream_tool_execution_start(
        ToolExecutionStartEvent(
            tool_call_id="tool-a",
            tool_name="read_file",
            args={"filepath": "a.py"},
        ),
        agent=object(),
        state=state,
        baseline_message_count=0,
    )
    await orchestrator._handle_stream_tool_execution_end(
        ToolExecutionEndEvent(
            tool_call_id="tool-a",
            tool_name="read_file",
            is_error=False,
            result=AgentToolResult(content=[TextContent(text="done")], details={}),
        ),
        agent=object(),
        state=state,
        baseline_message_count=0,
    )

    assert len(result_events) == 1
    assert result_events[0][0] == "read_file"
    assert result_events[0][1] == "completed"
    assert result_events[0][4] == pytest.approx(500.0)


def test_abort_cleanup_reconciles_in_flight_tool_state_and_dangling_messages() -> None:
    orchestrator, state, state_manager = _build_orchestrator_harness(
        start_events=[],
        result_events=[],
    )
    state.active_tool_call_ids.add("tool-a")
    state.last_stable_agent_message_count = 0
    orchestrator._active_stream_state = state

    registry = state_manager.session.runtime.tool_registry
    registry.register("tool-a", "read_file", {"filepath": "a.py"})
    registry.start("tool-a")
    state_manager.session._debug_raw_stream_accum = "partial output"

    fake_agent = SimpleNamespace(
        state=SimpleNamespace(
            messages=[
                AssistantMessage(
                    content=[
                        ToolCallContent(
                            id="tool-a",
                            name="read_file",
                            arguments={"filepath": "a.py"},
                        )
                    ],
                    stop_reason="tool_calls",
                    timestamp=None,
                )
            ]
        )
    )

    orchestrator._handle_abort_cleanup(
        get_logger(),
        agent=fake_agent,
        baseline_message_count=0,
        invalidate_cache=False,
    )

    assert registry.get("tool-a") is None
    assert orchestrator._active_stream_state is None
    assert len(state_manager.session.conversation.messages) == 1

    message = state_manager.session.conversation.messages[0]
    assert isinstance(message, AssistantMessage)
    assert len(message.content) == 1

    content_item = message.content[0]
    assert isinstance(content_item, TextContent)
    assert content_item.text == "[INTERRUPTED]\n\npartial output"
    assert state_manager.session.conversation.total_tokens == estimate_messages_tokens(
        state_manager.session.conversation.messages
    )


def test_abort_rollback_preserves_completed_turns_and_drops_in_flight() -> None:
    orchestrator, state, state_manager = _build_orchestrator_harness(
        start_events=[],
        result_events=[],
    )

    completed_assistant = AssistantMessage(
        content=[TextContent(text="completed response")],
        stop_reason="complete",
        timestamp=None,
    )
    completed_user = UserMessage(
        content=[TextContent(text="follow-up")],
    )
    in_flight_assistant = AssistantMessage(
        content=[
            ToolCallContent(
                id="tool-b",
                name="write_file",
                arguments={"path": "x.py"},
            )
        ],
        stop_reason="tool_calls",
        timestamp=None,
    )

    fake_agent = SimpleNamespace(
        state=SimpleNamespace(messages=[completed_assistant, completed_user, in_flight_assistant])
    )

    state.active_tool_call_ids.add("tool-b")
    state.last_stable_agent_message_count = 2
    orchestrator._active_stream_state = state

    registry = state_manager.session.runtime.tool_registry
    registry.register("tool-b", "write_file", {"path": "x.py"})
    registry.start("tool-b")
    state_manager.session._debug_raw_stream_accum = "partial write"

    orchestrator._handle_abort_cleanup(
        get_logger(),
        agent=fake_agent,
        baseline_message_count=0,
        invalidate_cache=False,
    )

    assert registry.get("tool-b") is None
    assert orchestrator._active_stream_state is None

    messages = state_manager.session.conversation.messages
    assert len(messages) == 3

    assert isinstance(messages[0], AssistantMessage)
    assert messages[0].content[0].text == "completed response"
    assert isinstance(messages[1], UserMessage)

    assert isinstance(messages[2], AssistantMessage)
    assert messages[2].content[0].text == "[INTERRUPTED]\n\npartial write"

    assert state_manager.session.conversation.total_tokens == estimate_messages_tokens(messages)


def test_persist_agent_messages_refreshes_total_tokens() -> None:
    orchestrator, _state, state_manager = _build_orchestrator_harness(
        start_events=[],
        result_events=[],
    )
    state_manager.session.conversation.messages = [
        AssistantMessage(content=[TextContent(text="external")], timestamp=None)
    ]
    state_manager.session.conversation.total_tokens = 0

    fake_agent = SimpleNamespace(
        state=SimpleNamespace(
            messages=[AssistantMessage(content=[TextContent(text="agent")], timestamp=None)]
        )
    )

    orchestrator._persist_agent_messages(fake_agent, baseline_message_count=0)

    assert state_manager.session.conversation.total_tokens == estimate_messages_tokens(
        state_manager.session.conversation.messages
    )
