from __future__ import annotations

import asyncio

import pytest
from tinyagent.agent_types import (
    AgentContext,
    AgentTool,
    AgentToolResult,
    AgentToolUpdateCallback,
    AssistantMessage,
    JsonObject,
    TextContent,
)

from tunacode.core.agents.agent_components import agent_config
from tunacode.core.session import StateManager


async def _wait_for_entered_count(entered_order: list[str], expected: int) -> None:
    while len(entered_order) < expected:
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_apply_tool_concurrency_limit_caps_in_flight_and_preserves_queue_order() -> None:
    entered_order: list[str] = []
    inflight = 0
    max_inflight = 0
    release_gate = asyncio.Event()

    async def _execute(
        tool_call_id: str,
        args: JsonObject,
        signal: asyncio.Event | None,
        on_update: AgentToolUpdateCallback,
    ) -> AgentToolResult:
        _ = (args, signal, on_update)
        nonlocal inflight
        nonlocal max_inflight

        inflight += 1
        max_inflight = max(max_inflight, inflight)
        entered_order.append(tool_call_id)
        await release_gate.wait()
        inflight -= 1
        return AgentToolResult(content=[TextContent(text=tool_call_id)], details={})

    raw_tools = [
        AgentTool(name=f"tool-{index}", label=f"tool-{index}", execute=_execute)
        for index in range(5)
    ]
    limited_tools = agent_config._apply_tool_concurrency_limit(
        raw_tools,
        max_parallel_tool_calls=3,
    )

    tasks = [
        asyncio.create_task(tool.execute(f"call-{index}", {}, None, lambda _update: None))
        for index, tool in enumerate(limited_tools)
    ]

    await asyncio.wait_for(_wait_for_entered_count(entered_order, expected=3), timeout=1.0)
    assert max_inflight == 3
    assert entered_order == ["call-0", "call-1", "call-2"]

    release_gate.set()
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=1.0)

    assert entered_order == ["call-0", "call-1", "call-2", "call-3", "call-4"]


def test_apply_tool_concurrency_limit_rejects_non_positive_max_parallel() -> None:
    with pytest.raises(ValueError, match="max_parallel_tool_calls must be >= 1"):
        agent_config._apply_tool_concurrency_limit([], max_parallel_tool_calls=0)


def test_should_stop_after_turn_updates_runtime_and_stops_after_limit() -> None:
    state_manager = StateManager()
    state_manager.session.user_config["settings"]["max_iterations"] = 1
    should_stop = agent_config._build_should_stop_after_turn(state_manager.session)
    message = AssistantMessage(content=[TextContent(text="done")])

    assert should_stop(message, [], AgentContext(), []) is False
    assert state_manager.session.runtime.iteration_count == 1
    assert state_manager.session.runtime.current_iteration == 1

    assert should_stop(message, [], AgentContext(), []) is True
    assert state_manager.session.runtime.iteration_count == 2
    assert state_manager.session.runtime.current_iteration == 2
