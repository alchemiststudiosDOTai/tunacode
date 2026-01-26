"""Tests for present_plan tool."""

from pathlib import Path

import pytest

from tunacode.constants import EXIT_PLAN_MODE_SENTINEL

from tunacode.tools.present_plan import (
    PLAN_APPROVED_MESSAGE,
    PLAN_EXITED_MESSAGE,
    PLAN_NOT_IN_PLAN_MODE,
    create_present_plan_tool,
)

from tunacode.core.state import StateManager


@pytest.fixture
def state_manager() -> StateManager:
    return StateManager()


@pytest.fixture(autouse=True)
def no_xml_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tunacode.tools.present_plan.load_prompt_from_xml", lambda _: None)


class TestPresentPlanTool:
    async def test_rejects_when_not_in_plan_mode(self, state_manager: StateManager) -> None:
        """present_plan should reject calls when not in plan mode."""
        present_plan = create_present_plan_tool(state_manager)
        state_manager.session.plan_mode = False

        result = await present_plan("# My Plan")
        assert result == PLAN_NOT_IN_PLAN_MODE

    async def test_auto_approves_without_callback(
        self, state_manager: StateManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without approval callback, plan is auto-approved."""
        present_plan = create_present_plan_tool(state_manager)
        state_manager.session.plan_mode = True
        monkeypatch.chdir(tmp_path)

        result = await present_plan("# My Plan\n\nSteps here.")
        assert result == PLAN_APPROVED_MESSAGE
        assert not state_manager.session.plan_mode
        assert (tmp_path / "PLAN.md").read_text() == "# My Plan\n\nSteps here."

    async def test_handles_approval_callback_approve(
        self, state_manager: StateManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When callback approves, plan is saved."""
        present_plan = create_present_plan_tool(state_manager)
        state_manager.session.plan_mode = True

        async def approve_callback(_: str) -> tuple[bool, str]:
            return (True, "")

        state_manager.session.plan_approval_callback = approve_callback
        monkeypatch.chdir(tmp_path)

        result = await present_plan("# Approved Plan")
        assert result == PLAN_APPROVED_MESSAGE
        assert not state_manager.session.plan_mode

    async def test_handles_approval_callback_deny(self, state_manager: StateManager) -> None:
        """When callback denies, feedback is returned."""
        present_plan = create_present_plan_tool(state_manager)
        state_manager.session.plan_mode = True

        async def deny_callback(_: str) -> tuple[bool, str]:
            return (False, "Need more detail")

        state_manager.session.plan_approval_callback = deny_callback

        result = await present_plan("# My Plan")
        assert "Need more detail" in result
        assert state_manager.session.plan_mode  # Still in plan mode

    async def test_handles_exit_sentinel(self, state_manager: StateManager) -> None:
        """When callback returns exit sentinel, plan mode is disabled."""
        present_plan = create_present_plan_tool(state_manager)
        state_manager.session.plan_mode = True

        async def exit_callback(_: str) -> tuple[bool, str]:
            return (False, EXIT_PLAN_MODE_SENTINEL)

        state_manager.session.plan_approval_callback = exit_callback

        result = await present_plan("# My Plan")
        assert result == PLAN_EXITED_MESSAGE
        assert not state_manager.session.plan_mode

    def test_signature_preserved(self, state_manager: StateManager) -> None:
        """Factory preserves function signature for pydantic-ai."""
        import inspect

        present_plan = create_present_plan_tool(state_manager)
        sig = inspect.signature(present_plan)
        params = list(sig.parameters.keys())
        assert "plan_content" in params


class TestPresentPlanRegistration:
    def test_present_plan_registered_in_agent(self, state_manager: StateManager) -> None:
        """Verify present_plan tool is registered with the agent."""
        from tunacode.core.agents.agent_components.agent_config import get_or_create_agent

        # Set up minimal config to avoid local mode
        state_manager.session.user_config = {
            "env": {"ANTHROPIC_API_KEY": "test-key"},
            "settings": {},
        }

        agent = get_or_create_agent("claude-sonnet-4-20250514", state_manager)
        tool_names = list(agent._function_toolset.tools.keys())

        assert "present_plan" in tool_names
