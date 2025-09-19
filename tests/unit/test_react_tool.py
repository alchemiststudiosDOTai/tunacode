import pytest

from tunacode.core.agents.main import _maybe_force_react_snapshot
from tunacode.core.state import StateManager
from tunacode.tools.react import ReactTool


@pytest.mark.asyncio
async def test_react_tool_records_think_and_observe():
    state_manager = StateManager()
    tool = ReactTool(state_manager=state_manager)

    await tool.execute(action="think", thoughts="Need info", next_action="read_file")
    await tool.execute(action="observe", result="Found the details")

    scratchpad = state_manager.session.react_scratchpad
    assert scratchpad["timeline"][0] == {
        "type": "think",
        "thoughts": "Need info",
        "next_action": "read_file",
    }
    assert scratchpad["timeline"][1] == {
        "type": "observe",
        "result": "Found the details",
    }


@pytest.mark.asyncio
async def test_forced_react_snapshot_runs_every_two_iterations():
    state_manager = StateManager()
    react_tool = ReactTool(state_manager=state_manager)

    for iteration in range(1, 12):
        await _maybe_force_react_snapshot(iteration, state_manager, react_tool, False)

    assert state_manager.session.react_forced_calls == 5
    timeline = state_manager.session.react_scratchpad["timeline"]
    assert len(timeline) == 5
    assert timeline[0]["type"] == "think"
    assert "Auto snapshot" in timeline[0]["thoughts"]
    guidance = getattr(state_manager.session, "react_guidance", [])
    assert len(guidance) == 5
    expected_iterations = [2, 4, 6, 8, 10]
    for entry, iteration in zip(guidance, expected_iterations):
        assert str(iteration) in entry
