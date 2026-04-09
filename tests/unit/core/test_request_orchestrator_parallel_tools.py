"""RequestOrchestrator tool lifecycle tests for parallel tinyagent batches."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from tinyagent.agent_types import (
    AgentToolResult,
    AssistantMessage,
    AssistantMessageEvent,
    MessageUpdateEvent,
    TextContent,
    ToolCallContent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolResultMessage,
    UserMessage,
)

from tunacode.types.canonical import ToolCallStatus
from tunacode.utils.messaging import estimate_messages_tokens

from tunacode.core.agents import main as agent_main
from tunacode.core.agents.agent_components.agent_streaming import _patch_dangling_tool_calls
from tunacode.core.agents.helpers import _TinyAgentStreamState
from tunacode.core.agents.main import RequestOrchestrator
from tunacode.core.logging.manager import get_logger
from tunacode.core.session import StateManager


class _FakeStreamAgent:
    def __init__(
        self,
        events: list[object],
        *,
        messages: list[object] | None = None,
        stream_error: Exception | None = None,
        on_stream_start: Callable[[_FakeStreamAgent], None] | None = None,
    ) -> None:
        self._events = events
        self._stream_error = stream_error
        self._on_stream_start = on_stream_start
        self.state = SimpleNamespace(error=None, messages=list(messages or []))

    def replace_messages(self, messages: list[object]) -> None:
        self.state.messages = list(messages)

    async def stream(self, _message: str):
        if self._on_stream_start is not None:
            self._on_stream_start(self)
        for event in self._events:
            yield event
        if self._stream_error is not None:
            raise self._stream_error


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
        baseline_message_count=0,
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


def test_abort_cleanup_patches_dangling_tool_calls_and_appends_interrupted() -> None:
    orchestrator, state, state_manager = _build_orchestrator_harness(
        start_events=[],
        result_events=[],
    )
    state.active_tool_call_ids.add("tool-a")
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

    orchestrator._handle_interrupted_stream_cleanup(
        get_logger(),
        agent=fake_agent,
        invalidate_cache=False,
    )

    assert registry.get("tool-a") is None
    assert orchestrator._active_stream_state is None

    messages = state_manager.session.conversation.messages
    assert len(messages) == 3

    assert isinstance(messages[0], AssistantMessage)
    assert isinstance(messages[0].content[0], ToolCallContent)
    assert messages[0].content[0].id == "tool-a"

    assert isinstance(messages[1], ToolResultMessage)
    assert messages[1].tool_call_id == "tool-a"
    assert messages[1].is_error is True
    assert messages[1].content[0].text == "Tool execution aborted"

    assert isinstance(messages[2], AssistantMessage)
    assert messages[2].content[0].text == "[INTERRUPTED]\n\npartial output"

    assert state_manager.session.conversation.total_tokens == estimate_messages_tokens(messages)


def test_uses_active_stream_baseline_for_cleanup() -> None:
    orchestrator, state, state_manager = _build_orchestrator_harness(
        start_events=[],
        result_events=[],
    )

    history_message = AssistantMessage(
        content=[TextContent(text="history")],
        stop_reason="complete",
        timestamp=None,
    )
    retry_assistant = AssistantMessage(
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
    state.baseline_message_count = 1
    state.active_tool_call_ids.add("tool-a")
    orchestrator._active_stream_state = state
    state_manager.session.conversation.messages = [history_message]

    registry = state_manager.session.runtime.tool_registry
    registry.register("tool-a", "read_file", {"filepath": "a.py"})
    registry.start("tool-a")

    fake_agent = SimpleNamespace(state=SimpleNamespace(messages=[history_message, retry_assistant]))

    orchestrator._handle_interrupted_stream_cleanup(
        get_logger(),
        agent=fake_agent,
        invalidate_cache=False,
    )

    messages = state_manager.session.conversation.messages
    assert len(messages) == 3
    assert isinstance(messages[0], AssistantMessage)
    assert messages[0].content[0].text == "history"
    assert isinstance(messages[1], AssistantMessage)
    assert isinstance(messages[1].content[0], ToolCallContent)
    assert messages[1].content[0].id == "tool-a"
    assert isinstance(messages[2], ToolResultMessage)
    assert messages[2].tool_call_id == "tool-a"
    assert registry.get("tool-a") is None


def test_abort_forward_patches_in_flight_turn_and_preserves_completed() -> None:
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
    orchestrator._active_stream_state = state

    registry = state_manager.session.runtime.tool_registry
    registry.register("tool-b", "write_file", {"path": "x.py"})
    registry.start("tool-b")
    state_manager.session._debug_raw_stream_accum = "partial write"

    orchestrator._handle_interrupted_stream_cleanup(
        get_logger(),
        agent=fake_agent,
        invalidate_cache=False,
    )

    assert registry.get("tool-b") is None
    assert orchestrator._active_stream_state is None

    messages = state_manager.session.conversation.messages
    assert len(messages) == 5

    assert isinstance(messages[0], AssistantMessage)
    assert messages[0].content[0].text == "completed response"
    assert isinstance(messages[1], UserMessage)

    assert isinstance(messages[2], AssistantMessage)
    assert isinstance(messages[2].content[0], ToolCallContent)
    assert messages[2].content[0].id == "tool-b"

    assert isinstance(messages[3], ToolResultMessage)
    assert messages[3].tool_call_id == "tool-b"
    assert messages[3].is_error is True
    assert messages[3].content[0].text == "Tool execution aborted"

    assert isinstance(messages[4], AssistantMessage)
    assert messages[4].content[0].text == "[INTERRUPTED]\n\npartial write"

    assert state_manager.session.conversation.total_tokens == estimate_messages_tokens(messages)


def test_abort_preserves_completed_tool_results_and_patches_remaining() -> None:
    orchestrator, state, state_manager = _build_orchestrator_harness(
        start_events=[],
        result_events=[],
    )

    assistant_msg = AssistantMessage(
        content=[
            ToolCallContent(id="tool-a", name="read_file", arguments={"filepath": "a.py"}),
            ToolCallContent(id="tool-b", name="write_file", arguments={"path": "x.py"}),
        ],
        stop_reason="tool_calls",
        timestamp=None,
    )
    completed_result = ToolResultMessage(
        tool_call_id="tool-a",
        tool_name="read_file",
        content=[TextContent(text="file contents here")],
        is_error=False,
    )

    fake_agent = SimpleNamespace(state=SimpleNamespace(messages=[assistant_msg, completed_result]))

    state.active_tool_call_ids.add("tool-b")
    orchestrator._active_stream_state = state

    registry = state_manager.session.runtime.tool_registry
    registry.register("tool-b", "write_file", {"path": "x.py"})
    registry.start("tool-b")
    state_manager.session._debug_raw_stream_accum = ""

    orchestrator._handle_interrupted_stream_cleanup(
        get_logger(),
        agent=fake_agent,
        invalidate_cache=False,
    )

    assert registry.get("tool-b") is None

    messages = state_manager.session.conversation.messages
    assert len(messages) == 3

    assert isinstance(messages[0], AssistantMessage)
    assert len(messages[0].content) == 2

    assert isinstance(messages[1], ToolResultMessage)
    assert messages[1].tool_call_id == "tool-a"
    assert messages[1].is_error is False
    assert messages[1].content[0].text == "file contents here"

    assert isinstance(messages[2], ToolResultMessage)
    assert messages[2].tool_call_id == "tool-b"
    assert messages[2].is_error is True
    assert messages[2].content[0].text == "Tool execution aborted"

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


def test_patch_dangling_tool_calls_noop_when_all_matched() -> None:
    messages: list = [
        AssistantMessage(
            content=[ToolCallContent(id="t1", name="read_file", arguments={})],
            stop_reason="tool_calls",
            timestamp=None,
        ),
        ToolResultMessage(
            tool_call_id="t1", tool_name="read_file", content=[TextContent(text="ok")]
        ),
    ]
    assert _patch_dangling_tool_calls(messages) == 0
    assert len(messages) == 2


def test_patch_dangling_tool_calls_noop_when_no_tool_calls() -> None:
    messages: list = [
        AssistantMessage(content=[TextContent(text="hello")], timestamp=None),
    ]
    assert _patch_dangling_tool_calls(messages) == 0
    assert len(messages) == 1


def test_patch_dangling_tool_calls_injects_for_multiple_missing() -> None:
    messages: list = [
        AssistantMessage(
            content=[
                ToolCallContent(id="t1", name="read_file", arguments={}),
                ToolCallContent(id="t2", name="write_file", arguments={}),
                ToolCallContent(id="t3", name="bash", arguments={}),
            ],
            stop_reason="tool_calls",
            timestamp=None,
        ),
        ToolResultMessage(
            tool_call_id="t1", tool_name="read_file", content=[TextContent(text="done")]
        ),
    ]
    patched = _patch_dangling_tool_calls(messages)
    assert patched == 2
    assert len(messages) == 4

    injected_ids = {m.tool_call_id for m in messages[2:]}
    assert injected_ids == {"t2", "t3"}
    for msg in messages[2:]:
        assert isinstance(msg, ToolResultMessage)
        assert msg.is_error is True
        assert msg.content[0].text == "Tool execution aborted"


@pytest.mark.asyncio
async def test_reraises_non_abort_exception_after_stream_cleanup() -> None:
    orchestrator, _state, state_manager = _build_orchestrator_harness(
        start_events=[],
        result_events=[],
    )
    state_manager.session._debug_raw_stream_accum = ""
    fake_agent = _FakeStreamAgent(
        [
            MessageUpdateEvent(
                assistant_message_event=AssistantMessageEvent(
                    type="text_delta",
                    delta="partial output",
                )
            ),
            ToolExecutionStartEvent(
                tool_call_id="tool-a",
                tool_name="read_file",
                args={"filepath": "a.py"},
            ),
        ],
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
        ],
        stream_error=RuntimeError("stream blew up"),
    )

    with pytest.raises(RuntimeError, match="stream blew up"):
        await orchestrator._run_stream(
            agent=fake_agent,
            max_iterations=4,
            baseline_message_count=0,
        )

    registry = state_manager.session.runtime.tool_registry
    assert registry.get("tool-a") is None
    assert orchestrator._active_stream_state is None

    messages = state_manager.session.conversation.messages
    assert len(messages) == 3
    assert isinstance(messages[0], AssistantMessage)
    assert isinstance(messages[0].content[0], ToolCallContent)
    assert isinstance(messages[1], ToolResultMessage)
    assert messages[1].is_error is True
    assert isinstance(messages[2], AssistantMessage)
    assert messages[2].content[0].text == "[INTERRUPTED]\n\npartial output"


@pytest.mark.asyncio
async def test_tool_start_callback_failure_cleanup() -> None:
    state_manager = StateManager()

    def _boom(_tool_name: str) -> None:
        raise RuntimeError("callback blew up")

    orchestrator = RequestOrchestrator(
        message="test",
        model="openai/gpt-4o",
        state_manager=state_manager,
        streaming_callback=None,
        tool_start_callback=_boom,
    )
    fake_agent = _FakeStreamAgent(
        [
            MessageUpdateEvent(
                assistant_message_event=AssistantMessageEvent(
                    type="text_delta",
                    delta="partial output",
                )
            ),
            ToolExecutionStartEvent(
                tool_call_id="tool-a",
                tool_name="read_file",
                args={"filepath": "a.py"},
            ),
        ],
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
        ],
    )

    with pytest.raises(RuntimeError, match="callback blew up"):
        await orchestrator._run_stream(
            agent=fake_agent,
            max_iterations=4,
            baseline_message_count=0,
        )

    registry = state_manager.session.runtime.tool_registry
    assert registry.get("tool-a") is None
    assert orchestrator._active_stream_state is None

    messages = state_manager.session.conversation.messages
    assert len(messages) == 3
    assert isinstance(messages[1], ToolResultMessage)
    assert messages[1].is_error is True
    assert isinstance(messages[2], AssistantMessage)
    assert messages[2].content[0].text == "[INTERRUPTED]\n\npartial output"


@pytest.mark.asyncio
async def test_tool_result_callback_failure_cleanup_preserves_completed_result() -> None:
    state_manager = StateManager()

    def _boom(
        _tool_name: str,
        _status: str,
        _args: dict[str, object],
        _result: AgentToolResult | None,
        _duration_ms: float | None,
    ) -> None:
        raise RuntimeError("callback blew up")

    completed_result = ToolResultMessage(
        tool_call_id="tool-a",
        tool_name="read_file",
        content=[TextContent(text="done")],
        is_error=False,
    )
    orchestrator = RequestOrchestrator(
        message="test",
        model="openai/gpt-4o",
        state_manager=state_manager,
        streaming_callback=None,
        tool_result_callback=_boom,
    )
    fake_agent = _FakeStreamAgent(
        [
            MessageUpdateEvent(
                assistant_message_event=AssistantMessageEvent(
                    type="text_delta",
                    delta="partial output",
                )
            ),
            ToolExecutionStartEvent(
                tool_call_id="tool-a",
                tool_name="read_file",
                args={"filepath": "a.py"},
            ),
            ToolExecutionEndEvent(
                tool_call_id="tool-a",
                tool_name="read_file",
                is_error=False,
                result=AgentToolResult(content=[TextContent(text="done")], details={}),
            ),
        ],
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
            ),
            completed_result,
        ],
    )

    with pytest.raises(RuntimeError, match="callback blew up"):
        await orchestrator._run_stream(
            agent=fake_agent,
            max_iterations=4,
            baseline_message_count=0,
        )

    registry = state_manager.session.runtime.tool_registry
    call = registry.get("tool-a")
    assert call is not None
    assert call.status is ToolCallStatus.COMPLETED
    assert orchestrator._active_stream_state is None

    messages = state_manager.session.conversation.messages
    assert len(messages) == 3
    assert isinstance(messages[1], ToolResultMessage)
    assert messages[1].tool_call_id == "tool-a"
    assert messages[1].is_error is False
    assert messages[1].content[0].text == "done"
    assert isinstance(messages[2], AssistantMessage)
    assert messages[2].content[0].text == "[INTERRUPTED]\n\npartial output"


@pytest.mark.asyncio
async def test_retry_stream_cleanup_baseline() -> None:
    orchestrator, _state, state_manager = _build_orchestrator_harness(
        start_events=[],
        result_events=[],
    )
    pre_request_history = [
        AssistantMessage(
            content=[TextContent(text="history")],
            stop_reason="complete",
            timestamp=None,
        )
    ]
    state_manager.session.conversation.messages = list(pre_request_history)
    state_manager.session.conversation.max_tokens = 128
    state_manager.session._debug_raw_stream_accum = ""

    async def _force_compact(history: list[object]) -> list[object]:
        return list(history)

    orchestrator._force_compact_history = _force_compact  # type: ignore[method-assign]

    retry_assistant = AssistantMessage(
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

    def _prepare_retry(agent: _FakeStreamAgent) -> None:
        agent.state.messages = [*agent.state.messages, retry_assistant]

    fake_agent = _FakeStreamAgent(
        [
            ToolExecutionStartEvent(
                tool_call_id="tool-a",
                tool_name="read_file",
                args={"filepath": "a.py"},
            )
        ],
        messages=list(pre_request_history),
        stream_error=RuntimeError("retry blew up"),
        on_stream_start=_prepare_retry,
    )
    fake_agent.state.error = "maximum context length"

    with pytest.raises(RuntimeError, match="retry blew up"):
        await orchestrator._retry_after_context_overflow_if_needed(
            agent=fake_agent,
            max_iterations=4,
            pre_request_history=pre_request_history,
        )

    registry = state_manager.session.runtime.tool_registry
    assert registry.get("tool-a") is None
    assert orchestrator._active_stream_state is None

    messages = state_manager.session.conversation.messages
    assert len(messages) == 3
    assert isinstance(messages[0], AssistantMessage)
    assert messages[0].content[0].text == "history"
    assert isinstance(messages[1], AssistantMessage)
    assert isinstance(messages[1].content[0], ToolCallContent)
    assert messages[1].content[0].id == "tool-a"
    assert isinstance(messages[2], ToolResultMessage)
    assert messages[2].tool_call_id == "tool-a"
