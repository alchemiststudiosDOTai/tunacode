"""Tests for agent cache invalidation on abort.

Bug: When user hits ESC to abort a request, the HTTP client in the cached agent
may have a broken connection. The next request reuses this broken agent and hangs.

Fix: Invalidate agent cache (both global and session-level) on abort.
"""

from unittest.mock import MagicMock

import pytest
from tinyagent import Agent

from tunacode.infrastructure.cache.caches.agents import clear_agents, get_agent, set_agent

from tunacode.core.agents.agent_components.agent_config import invalidate_agent_cache


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
