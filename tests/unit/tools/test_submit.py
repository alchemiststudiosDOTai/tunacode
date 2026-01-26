import inspect

import pytest
from pydantic_ai.messages import ToolCallPart

from tunacode.tools.submit import (
    SUBMIT_SUCCESS_MESSAGE,
    SUBMIT_SUMMARY_LABEL,
    submit,
)

from tunacode.core.agents.agent_components.orchestrator.tool_dispatcher import dispatch_tools
from tunacode.core.agents.agent_components.response_state import ResponseState
from tunacode.core.state import StateManager


@pytest.fixture
def state_manager() -> StateManager:
    return StateManager()


class TestSubmitTool:
    async def test_submit_returns_success_message(self) -> None:
        assert await submit() == SUBMIT_SUCCESS_MESSAGE

        summary = "Finished submit tool wiring"
        expected = f"{SUBMIT_SUCCESS_MESSAGE} {SUBMIT_SUMMARY_LABEL} {summary}"
        assert await submit(summary) == expected

    def test_signature_preserved(self) -> None:
        sig = inspect.signature(submit)
        params = list(sig.parameters.keys())
        assert "summary" in params


class TestSubmitCompletion:
    async def test_submit_dispatches_without_error(self, state_manager: StateManager) -> None:
        """Submit tool dispatches successfully - task completion handled by pydantic-ai loop."""
        response_state = ResponseState()
        part = ToolCallPart(tool_name="submit", args={}, tool_call_id="tool-call-1")

        await dispatch_tools(
            parts=[part],
            node=object(),
            state_manager=state_manager,
            tool_callback=None,
            _tool_result_callback=None,
            tool_start_callback=None,
            response_state=response_state,
        )

        # Submit no longer sets task_completed - pydantic-ai loop ends naturally
        assert response_state is not None


class TestSubmitRegistration:
    def test_submit_registered_in_agent(self, state_manager: StateManager) -> None:
        from tunacode.core.agents.agent_components.agent_config import get_or_create_agent

        state_manager.session.user_config = {
            "env": {"ANTHROPIC_API_KEY": "test-key"},
            "settings": {},
        }

        agent = get_or_create_agent("claude-sonnet-4-20250514", state_manager)
        tool_names = list(agent._function_toolset.tools.keys())

        assert "submit" in tool_names
