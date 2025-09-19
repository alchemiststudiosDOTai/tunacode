import pytest

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
