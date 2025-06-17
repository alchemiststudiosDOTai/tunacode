import asyncio
from pathlib import Path

from tunacode.core.agents.react_agent import ReActAgent
from tunacode.core.agents.planner_schema import Task
from tunacode.core.state import StateManager
from tunacode.core.tool_handler import ToolHandler


async def test_tool_handler_dispatch(tmp_path):
    state = StateManager()
    handler = ToolHandler(state)
    test_file = tmp_path / "sample.txt"
    test_file.write_text("hello")

    task = Task(id=1, description="read", mutate=False, tool="read_file", args={"file_path": str(test_file)})
    result = await handler.execute(task)
    assert "hello" in result


async def test_react_agent_run(tmp_path):
    state = StateManager()
    agent = ReActAgent(state)

    temp = tmp_path / "demo.txt"
    temp.write_text("data")

    async def fake_plan(request, model):
        return [
            Task(id=1, description="read demo", mutate=False, tool="read_file", args={"file_path": str(temp)})
        ]

    agent.plan = fake_plan
    results = await agent.run("demo")
    assert results and "data" in results[0]["output"]


if __name__ == "__main__":
    asyncio.run(test_tool_handler_dispatch(Path(".")))
    asyncio.run(test_react_agent_run(Path(".")))
