import pytest
from pydantic_ai.exceptions import ModelRetry

from tunacode.tools.todo import create_todoclear_tool, create_todoread_tool, create_todowrite_tool

from tunacode.core.state import StateManager


@pytest.fixture
def state_manager() -> StateManager:
    return StateManager()


@pytest.fixture(autouse=True)
def no_xml_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tunacode.tools.todo.load_prompt_from_xml", lambda _: None)


class TestTodoTools:
    async def test_todowrite_enforces_single_in_progress(self, state_manager: StateManager) -> None:
        todowrite = create_todowrite_tool(state_manager)

        with pytest.raises(ModelRetry, match="Only 1 todo may be"):
            await todowrite(
                [
                    {"content": "One", "status": "in_progress", "activeForm": "Doing one"},
                    {"content": "Two", "status": "in_progress", "activeForm": "Doing two"},
                ]
            )

    async def test_write_read_clear_round_trip(self, state_manager: StateManager) -> None:
        todowrite = create_todowrite_tool(state_manager)
        todoread = create_todoread_tool(state_manager)
        todoclear = create_todoclear_tool(state_manager)

        await todowrite(
            [
                {"content": "First", "status": "in_progress", "activeForm": "Doing first"},
                {"content": "Second", "status": "pending", "activeForm": "Doing second"},
            ]
        )

        output = await todoread()
        assert "1. [>] First (Doing first)" in output
        assert "2. [ ] Second" in output

        cleared = await todoclear()
        assert cleared == "Todo list cleared."
        assert await todoread() == "No todos in list."
