"""Tests for agent cache invalidation on abort.

Bug: When user hits ESC to abort a request, the HTTP client in the cached agent
may have a broken connection. The next request reuses this broken agent and hangs.

Fix: Invalidate agent cache (both global and session-level) on abort.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tinyagent.agent import Agent

from tunacode.infrastructure.cache.caches.agents import clear_agents, get_agent, set_agent

from tunacode.core.agents.agent_components import agent_config
from tunacode.core.agents.agent_components.agent_config import invalidate_agent_cache
from tunacode.core.session import StateManager


@pytest.fixture
def clean_caches():
    """Ensure caches are clean before and after each test."""
    clear_agents()
    yield
    clear_agents()


@pytest.fixture
def mock_session():
    """Create a mock session with agent storage."""
    session = MagicMock()
    session.agents = {}
    session.agent_versions = {}
    return session


@pytest.fixture
def mock_state_manager(mock_session):
    """Create a mock state manager."""
    state_manager = MagicMock()
    state_manager.session = mock_session
    return state_manager


def test_abort_should_invalidate_agent_cache(clean_caches, mock_state_manager):
    """After abort, caches should be cleared to force a fresh HTTP client."""

    model = "test:model"
    agent = Agent()
    version = 12345

    # Populate both caches (simulating normal agent creation).
    set_agent(model, agent=agent, version=version)
    mock_state_manager.session.agents[model] = agent
    mock_state_manager.session.agent_versions[model] = version

    assert get_agent(model, expected_version=version) is agent
    assert model in mock_state_manager.session.agents

    invalidated = invalidate_agent_cache(model, mock_state_manager)

    assert invalidated is True
    assert get_agent(model, expected_version=version) is None
    assert model not in mock_state_manager.session.agents
    assert model not in mock_state_manager.session.agent_versions


def test_invalidate_returns_false_when_not_cached(clean_caches, mock_state_manager):
    """invalidate_agent_cache returns False if the agent wasn't cached."""

    model = "uncached:model"

    assert get_agent(model, expected_version=0) is None

    invalidated = invalidate_agent_cache(model, mock_state_manager)
    assert invalidated is False


def test_get_or_create_agent_does_not_reuse_module_cached_agent_across_sessions(
    clean_caches,
    monkeypatch: pytest.MonkeyPatch,
):
    """Session-bound agent options must not be reused from the module cache."""

    created_session_ids: list[str] = []

    class FakeAgent:
        def __init__(self, options):
            self.options = options
            self._state = SimpleNamespace(system_prompt=None)
            created_session_ids.append(options.session_id)

        def set_system_prompt(self, system_prompt: str) -> None:
            self._state.system_prompt = system_prompt

        def set_model(self, model: object) -> None:
            self.model = model

        def set_tools(self, tools: list[object]) -> None:
            self.tools = tools

    monkeypatch.setattr(agent_config, "Agent", FakeAgent)
    monkeypatch.setattr(
        agent_config,
        "load_system_prompt",
        lambda _base_path, model=None: "SYSTEM",
    )
    monkeypatch.setattr(agent_config, "load_tunacode_context", lambda: "CONTEXT")
    monkeypatch.setattr(agent_config, "load_models_registry", lambda: None)
    monkeypatch.setattr(agent_config, "_build_tools", lambda **kwargs: [])
    monkeypatch.setattr(agent_config, "_build_tinyagent_model", lambda model, config: object())

    first_state_manager = StateManager()
    first_state_manager.session.session_id = "session-1"
    first_state_manager.session.user_config["settings"]["max_tokens"] = 4096
    first_agent = agent_config.get_or_create_agent(
        first_state_manager.session.current_model,
        first_state_manager,
    )

    monkeypatch.setattr(
        agent_config.agents_cache,
        "get_agent",
        lambda model, *, expected_version: first_agent,
    )

    second_state_manager = StateManager()
    second_state_manager.session.session_id = "session-2"
    second_state_manager.session.user_config["settings"]["max_tokens"] = 4096
    second_agent = agent_config.get_or_create_agent(
        second_state_manager.session.current_model,
        second_state_manager,
    )

    assert first_agent is not second_agent
    assert first_agent.options.session_id == "session-1"
    assert second_agent.options.session_id == "session-2"
    assert created_session_ids == ["session-1", "session-2"]
