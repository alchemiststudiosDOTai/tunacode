"""Tests for present_plan tool registration and signature preservation.

These tests prevent regression of the plan-tool-registration-failure bug where:
1. present_plan was never registered with the agent
2. Factory function didn't preserve __signature__ for pydantic-ai schema generation
"""

import inspect
from unittest.mock import MagicMock

from tunacode.tools.present_plan import create_present_plan_tool


class TestPresentPlanSignature:
    """Verify present_plan factory preserves signature for pydantic-ai."""

    def test_factory_returns_callable(self):
        """Factory should return an async callable."""
        state_manager = MagicMock()
        state_manager.session.plan_mode = True
        tool = create_present_plan_tool(state_manager)
        assert callable(tool)
        assert inspect.iscoroutinefunction(tool)

    def test_factory_preserves_signature(self):
        """Factory must preserve __signature__ for pydantic-ai schema generation.

        Without __signature__, pydantic-ai can't inspect parameter types,
        causing LLMs to hallucinate wrong argument types.
        """
        state_manager = MagicMock()
        tool = create_present_plan_tool(state_manager)

        assert hasattr(tool, "__signature__"), (
            "present_plan missing __signature__ - pydantic-ai cannot generate tool schema"
        )

        sig = tool.__signature__
        assert sig is not None
        params = list(sig.parameters.keys())
        assert "plan_content" in params, f"Expected 'plan_content' param, got {params}"

    def test_signature_has_type_annotations(self):
        """Signature should include type annotations for schema generation."""
        state_manager = MagicMock()
        tool = create_present_plan_tool(state_manager)
        sig = inspect.signature(tool)

        plan_content_param = sig.parameters.get("plan_content")
        assert plan_content_param is not None
        # With `from __future__ import annotations`, annotations are strings
        annotation = plan_content_param.annotation
        assert annotation is str or annotation == "str", (
            f"plan_content should be str, got {annotation}"
        )

    def test_has_docstring(self):
        """Tool must have a docstring for LLM to understand its purpose."""
        state_manager = MagicMock()
        tool = create_present_plan_tool(state_manager)
        assert tool.__doc__, "present_plan has no docstring"
        assert len(tool.__doc__) > 20, "Docstring too short to be useful"


class TestPlanToolRegistration:
    """Verify present_plan is registered when plan_mode is active."""

    def test_agent_includes_present_plan_in_plan_mode(self):
        """Agent should have present_plan tool when plan_mode=True."""
        from tunacode.core.agents.agent_components.agent_config import (
            clear_all_caches,
            get_or_create_agent,
        )

        # Clear caches to ensure fresh agent
        clear_all_caches()

        state_manager = MagicMock()
        state_manager.session.plan_mode = True
        # Provide fake API key so provider doesn't raise
        state_manager.session.user_config = {
            "settings": {},
            "env": {"ANTHROPIC_API_KEY": "test-key-not-used"},
        }
        state_manager.session.agents = {}
        state_manager.session.agent_versions = {}

        agent = get_or_create_agent("anthropic:claude-sonnet-4-20250514", state_manager)

        tool_names = list(agent._function_toolset.tools.keys())
        assert "present_plan" in tool_names, (
            f"present_plan not registered in plan_mode. Tools: {tool_names}"
        )

    def test_agent_excludes_present_plan_outside_plan_mode(self):
        """Agent should NOT have present_plan tool when plan_mode=False."""
        from tunacode.core.agents.agent_components.agent_config import (
            clear_all_caches,
            get_or_create_agent,
        )

        # Clear caches to ensure fresh agent
        clear_all_caches()

        state_manager = MagicMock()
        state_manager.session.plan_mode = False
        state_manager.session.user_config = {
            "settings": {},
            "env": {"ANTHROPIC_API_KEY": "test-key-not-used"},
        }
        state_manager.session.agents = {}
        state_manager.session.agent_versions = {}

        agent = get_or_create_agent("anthropic:claude-sonnet-4-20250514", state_manager)

        tool_names = list(agent._function_toolset.tools.keys())
        assert "present_plan" not in tool_names, (
            f"present_plan should NOT be registered outside plan_mode. Tools: {tool_names}"
        )

    def test_agent_cache_invalidates_on_plan_mode_toggle(self):
        """Agent should be recreated when plan_mode changes."""
        from tunacode.core.agents.agent_components.agent_config import (
            clear_all_caches,
            get_or_create_agent,
        )

        clear_all_caches()

        state_manager = MagicMock()
        state_manager.session.user_config = {
            "settings": {},
            "env": {"ANTHROPIC_API_KEY": "test-key-not-used"},
        }
        state_manager.session.agents = {}
        state_manager.session.agent_versions = {}

        # First call: plan_mode=False
        state_manager.session.plan_mode = False
        agent1 = get_or_create_agent("anthropic:claude-sonnet-4-20250514", state_manager)
        tools1 = list(agent1._function_toolset.tools.keys())

        # Second call: plan_mode=True (should create new agent)
        state_manager.session.plan_mode = True
        agent2 = get_or_create_agent("anthropic:claude-sonnet-4-20250514", state_manager)
        tools2 = list(agent2._function_toolset.tools.keys())

        assert "present_plan" not in tools1
        assert "present_plan" in tools2
        assert agent1 is not agent2, "Agent should be recreated when plan_mode changes"
