"""Tests for tool arguments retained across tinyagent stream events."""

from __future__ import annotations

from tinyagent.agent import Agent
from tinyagent.agent_types import ToolExecutionEndEvent, ToolExecutionStartEvent

from tunacode.core.agents.helpers import _TinyAgentStreamState
from tunacode.core.agents.main import RequestOrchestrator
from tunacode.core.session import StateManager


async def test_tool_end_uses_args_retained_from_start_event() -> None:
    callback_calls: list[tuple[object, ...]] = []
    state_manager = StateManager()
    orchestrator = RequestOrchestrator(
        message="test",
        model="openai/gpt-4o",
        state_manager=state_manager,
        streaming_callback=None,
        tool_result_callback=lambda *args: callback_calls.append(args),
    )
    state = _TinyAgentStreamState(
        runtime=state_manager.session.runtime,
        baseline_message_count=0,
        tool_start_times={},
        tool_args_by_call_id={},
        active_tool_call_ids=set(),
        batch_tool_call_ids=set(),
    )
    agent = Agent()

    await orchestrator._handle_stream_tool_execution_start(
        ToolExecutionStartEvent(
            tool_call_id="call-1",
            tool_name="read_file",
            args={"filepath": "src/example.py"},
        ),
        agent=agent,
        state=state,
        baseline_message_count=0,
    )
    await orchestrator._handle_stream_tool_execution_end(
        ToolExecutionEndEvent(
            tool_call_id="call-1",
            tool_name="read_file",
        ),
        agent=agent,
        state=state,
        baseline_message_count=0,
    )

    assert len(callback_calls) == 1
    assert callback_calls[0][0:3] == (
        "read_file",
        "completed",
        {"filepath": "src/example.py"},
    )
    assert state.tool_args_by_call_id == {}
