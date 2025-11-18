"""Tests for tunacode.core.agents.main module.

Golden baseline tests for agent orchestration components including:
- EmptyResponseHandler: empty response tracking and intervention
- IterationManager: productivity tracking, forced actions, iteration limits
- ReactSnapshotManager: snapshot scheduling and guidance injection
- RequestOrchestrator: main request processing flow
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tunacode.core.agents.main import (
    AgentConfig,
    EmptyResponseHandler,
    IterationManager,
    ReactSnapshotManager,
    RequestContext,
    RequestOrchestrator,
    check_query_satisfaction,
    get_agent_tool,
)
from tunacode.core.state import StateManager

if TYPE_CHECKING:
    from tunacode.types import ModelName


# Fixtures


@pytest.fixture
def state_manager() -> StateManager:
    """Create a StateManager with initialized session."""
    manager = StateManager()
    # SessionState is already created in __init__
    # Initialize additional attributes that aren't in SessionState defaults
    session = manager.session
    session.batch_counter = 0
    session.original_query = ""
    # Initialize dynamic attributes used by handlers
    setattr(session, "consecutive_empty_responses", 0)
    setattr(session, "request_id", "test-req-id")
    return manager


@pytest.fixture
def agent_config() -> AgentConfig:
    """Create default agent configuration."""
    return AgentConfig(
        max_iterations=15,
        unproductive_limit=3,
        forced_react_interval=2,
        forced_react_limit=5,
        debug_metrics=False,
    )


# AgentConfig Tests


def test_agent_config_defaults() -> None:
    """Test AgentConfig initializes with correct defaults."""
    config = AgentConfig()

    assert config.max_iterations == 15
    assert config.unproductive_limit == 3
    assert config.forced_react_interval == 2
    assert config.forced_react_limit == 5
    assert config.debug_metrics is False


def test_agent_config_custom_values() -> None:
    """Test AgentConfig accepts custom values."""
    config = AgentConfig(
        max_iterations=20,
        unproductive_limit=5,
        forced_react_interval=3,
        forced_react_limit=10,
        debug_metrics=True,
    )

    assert config.max_iterations == 20
    assert config.unproductive_limit == 5
    assert config.forced_react_interval == 3
    assert config.forced_react_limit == 10
    assert config.debug_metrics is True


# RequestContext Tests


def test_request_context_creation() -> None:
    """Test RequestContext stores request metadata."""
    ctx = RequestContext(
        request_id="test-123",
        max_iterations=15,
        debug_metrics=True,
    )

    assert ctx.request_id == "test-123"
    assert ctx.max_iterations == 15
    assert ctx.debug_metrics is True


# EmptyResponseHandler Tests


def test_empty_response_handler_tracks_empty(state_manager: StateManager) -> None:
    """Test EmptyResponseHandler increments counter on empty response."""
    handler = EmptyResponseHandler(state_manager)

    handler.track(is_empty=True)
    assert state_manager.session.consecutive_empty_responses == 1

    handler.track(is_empty=True)
    assert state_manager.session.consecutive_empty_responses == 2


def test_empty_response_handler_resets_on_non_empty(state_manager: StateManager) -> None:
    """Test EmptyResponseHandler resets counter on non-empty response."""
    handler = EmptyResponseHandler(state_manager)

    handler.track(is_empty=True)
    handler.track(is_empty=True)
    assert state_manager.session.consecutive_empty_responses == 2

    handler.track(is_empty=False)
    assert state_manager.session.consecutive_empty_responses == 0


def test_empty_response_handler_should_intervene(state_manager: StateManager) -> None:
    """Test EmptyResponseHandler triggers intervention at threshold."""
    handler = EmptyResponseHandler(state_manager)

    # No intervention initially
    assert handler.should_intervene() is False

    # Intervention after 1 empty response
    handler.track(is_empty=True)
    assert handler.should_intervene() is True


@pytest.mark.asyncio
async def test_empty_response_handler_prompt_action(state_manager: StateManager) -> None:
    """Test EmptyResponseHandler calls intervention and resets counter."""
    handler = EmptyResponseHandler(state_manager)
    state_manager.session.consecutive_empty_responses = 2

    with patch(
        "tunacode.core.agents.main.ac.handle_empty_response", new_callable=AsyncMock
    ) as mock_handle:
        await handler.prompt_action("test message", "test reason", 5)

        # Verify handle_empty_response was called
        mock_handle.assert_called_once()
        call_args = mock_handle.call_args[0]
        assert call_args[0] == "test message"
        assert call_args[1] == "test reason"
        assert call_args[2] == 5

        # Verify counter was reset
        assert state_manager.session.consecutive_empty_responses == 0


# IterationManager Tests


def test_iteration_manager_tracks_productivity_with_tools(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test IterationManager resets unproductive counter when tools are used."""
    manager = IterationManager(state_manager, agent_config)

    # Simulate unproductive iterations
    manager.unproductive_iterations = 3

    # Track productive iteration
    manager.track_productivity(had_tool_use=True, iteration=5)

    assert manager.unproductive_iterations == 0
    assert manager.last_productive_iteration == 5


def test_iteration_manager_tracks_unproductive_iterations(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test IterationManager increments counter when no tools used."""
    manager = IterationManager(state_manager, agent_config)

    manager.track_productivity(had_tool_use=False, iteration=1)
    assert manager.unproductive_iterations == 1

    manager.track_productivity(had_tool_use=False, iteration=2)
    assert manager.unproductive_iterations == 2

    manager.track_productivity(had_tool_use=False, iteration=3)
    assert manager.unproductive_iterations == 3


def test_iteration_manager_should_force_action(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test IterationManager forces action after unproductive limit."""
    manager = IterationManager(state_manager, agent_config)

    # Mock ResponseState
    response_state = Mock()
    response_state.task_completed = False

    # Below limit
    manager.unproductive_iterations = 2
    assert manager.should_force_action(response_state) is False

    # At limit
    manager.unproductive_iterations = 3
    assert manager.should_force_action(response_state) is True

    # Don't force if task completed
    response_state.task_completed = True
    assert manager.should_force_action(response_state) is False


def test_iteration_manager_updates_counters(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test IterationManager updates session iteration counters."""
    manager = IterationManager(state_manager, agent_config)

    manager.update_counters(iteration=5)

    assert state_manager.session.current_iteration == 5
    assert state_manager.session.iteration_count == 5


@pytest.mark.asyncio
async def test_iteration_manager_handle_iteration_limit(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test IterationManager handles reaching iteration limit."""
    manager = IterationManager(state_manager, agent_config)
    state_manager.session.tool_calls = [{"tool": "test", "args": {}}]

    response_state = Mock()
    response_state.task_completed = False
    response_state.awaiting_user_guidance = False

    with patch("tunacode.core.agents.main.ac.create_user_message") as mock_create:
        await manager.handle_iteration_limit(iteration=15, response_state=response_state)

        # Should create user message
        mock_create.assert_called_once()

        # Should set awaiting_user_guidance
        assert response_state.awaiting_user_guidance is True


@pytest.mark.asyncio
async def test_iteration_manager_no_action_when_below_limit(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test IterationManager doesn't intervene when below iteration limit."""
    manager = IterationManager(state_manager, agent_config)

    response_state = Mock()
    response_state.task_completed = False

    with patch("tunacode.core.agents.main.ac.create_user_message") as mock_create:
        await manager.handle_iteration_limit(iteration=10, response_state=response_state)

        # Should not create user message
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_iteration_manager_force_action_if_unproductive(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test IterationManager forces action when unproductive limit reached."""
    manager = IterationManager(state_manager, agent_config)
    manager.unproductive_iterations = 3
    manager.last_productive_iteration = 2

    response_state = Mock()
    response_state.task_completed = False

    with patch("tunacode.core.agents.main.ac.create_user_message") as mock_create:
        await manager.force_action_if_unproductive(
            message="test",
            iteration=5,
            response_state=response_state,
        )

        # Should create nudge message
        mock_create.assert_called_once()

        # Should reset unproductive counter
        assert manager.unproductive_iterations == 0


@pytest.mark.asyncio
async def test_iteration_manager_ask_for_clarification(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test IterationManager asks for clarification."""
    manager = IterationManager(state_manager, agent_config)
    state_manager.session.tool_calls = []
    state_manager.session.original_query = "test query"

    with patch("tunacode.core.agents.main.ac.create_user_message") as mock_create:
        await manager.ask_for_clarification(iteration=5)

        mock_create.assert_called_once()


# ReactSnapshotManager Tests


def test_react_snapshot_manager_should_snapshot_before_interval(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test ReactSnapshotManager doesn't snapshot before interval."""
    mock_tool = Mock()
    manager = ReactSnapshotManager(state_manager, mock_tool, agent_config)

    # Before interval
    assert manager.should_snapshot(iteration=1) is False


def test_react_snapshot_manager_should_snapshot_at_interval(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test ReactSnapshotManager snapshots at correct intervals."""
    mock_tool = Mock()
    manager = ReactSnapshotManager(state_manager, mock_tool, agent_config)

    # At interval (2, 4, 6, etc.)
    assert manager.should_snapshot(iteration=2) is True
    assert manager.should_snapshot(iteration=4) is True

    # Not at interval
    assert manager.should_snapshot(iteration=3) is False
    assert manager.should_snapshot(iteration=5) is False


def test_react_snapshot_manager_respects_limit(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test ReactSnapshotManager respects forced call limit."""
    mock_tool = Mock()
    manager = ReactSnapshotManager(state_manager, mock_tool, agent_config)

    # Set forced calls to limit
    state_manager.session.react_forced_calls = 5

    # Should not snapshot even at interval
    assert manager.should_snapshot(iteration=2) is False


@pytest.mark.asyncio
async def test_react_snapshot_manager_capture_snapshot(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test ReactSnapshotManager captures snapshot and injects guidance."""
    mock_tool = Mock()
    mock_tool.execute = AsyncMock()

    manager = ReactSnapshotManager(state_manager, mock_tool, agent_config)

    # Setup timeline
    state_manager.session.react_scratchpad = {
        "timeline": [{"thoughts": "test thought", "next_action": "continue"}]
    }
    state_manager.session.tool_calls = [{"tool": "grep", "args": {"pattern": "test_pattern"}}]

    # Mock agent_run_ctx
    mock_ctx = Mock()
    mock_ctx.messages = []

    await manager.capture_snapshot(iteration=2, agent_run_ctx=mock_ctx, show_debug=False)

    # Verify tool was called
    mock_tool.execute.assert_called_once()

    # Verify forced calls incremented
    assert state_manager.session.react_forced_calls == 1

    # Verify guidance added
    assert len(state_manager.session.react_guidance) == 1
    assert "React snapshot" in state_manager.session.react_guidance[0]


@pytest.mark.asyncio
async def test_react_snapshot_manager_handles_errors_gracefully(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Test ReactSnapshotManager handles errors without crashing."""
    mock_tool = Mock()
    mock_tool.execute = AsyncMock(side_effect=Exception("Test error"))

    manager = ReactSnapshotManager(state_manager, mock_tool, agent_config)

    # Should not raise
    await manager.capture_snapshot(iteration=2, agent_run_ctx=None, show_debug=False)


# RequestOrchestrator Tests


@pytest.fixture
def mock_model() -> ModelName:
    """Create a mock model name."""
    return "claude-3-5-sonnet-20241022"  # type: ignore[return-value]


def test_request_orchestrator_initialization(
    state_manager: StateManager, mock_model: ModelName
) -> None:
    """Test RequestOrchestrator initializes with correct configuration."""
    orchestrator = RequestOrchestrator(
        message="test message",
        model=mock_model,
        state_manager=state_manager,
        tool_callback=None,
        streaming_callback=None,
        usage_tracker=None,
    )

    assert orchestrator.message == "test message"
    assert orchestrator.model == mock_model
    assert orchestrator.state_manager == state_manager
    assert isinstance(orchestrator.config, AgentConfig)
    assert isinstance(orchestrator.empty_handler, EmptyResponseHandler)
    assert isinstance(orchestrator.iteration_manager, IterationManager)
    assert isinstance(orchestrator.react_manager, ReactSnapshotManager)


def test_request_orchestrator_custom_config(
    state_manager: StateManager, mock_model: ModelName
) -> None:
    """Test RequestOrchestrator respects custom settings from session."""
    state_manager.session.user_config = {
        "settings": {
            "max_iterations": 20,
            "debug_metrics": True,
        }
    }

    orchestrator = RequestOrchestrator(
        message="test",
        model=mock_model,
        state_manager=state_manager,
        tool_callback=None,
        streaming_callback=None,
        usage_tracker=None,
    )

    assert orchestrator.config.max_iterations == 20
    assert orchestrator.config.debug_metrics is True


def test_request_orchestrator_reset_session_state(
    state_manager: StateManager, mock_model: ModelName
) -> None:
    """Test RequestOrchestrator resets session state properly."""
    # Set some existing state
    state_manager.session.current_iteration = 10
    state_manager.session.tool_calls = [{"tool": "old"}]

    orchestrator = RequestOrchestrator(
        message="test",
        model=mock_model,
        state_manager=state_manager,
        tool_callback=None,
        streaming_callback=None,
        usage_tracker=None,
    )

    orchestrator._reset_session_state()

    assert state_manager.session.current_iteration == 0
    assert state_manager.session.iteration_count == 0
    assert state_manager.session.tool_calls == []
    assert state_manager.session.react_forced_calls == 0
    assert state_manager.session.react_guidance == []
    assert state_manager.session.batch_counter == 0


def test_request_orchestrator_set_original_query_once(
    state_manager: StateManager, mock_model: ModelName
) -> None:
    """Test RequestOrchestrator only sets original query once."""
    orchestrator = RequestOrchestrator(
        message="test",
        model=mock_model,
        state_manager=state_manager,
        tool_callback=None,
        streaming_callback=None,
        usage_tracker=None,
    )

    orchestrator._set_original_query_once("first query")
    assert state_manager.session.original_query == "first query"

    # Second call should not override
    orchestrator._set_original_query_once("second query")
    assert state_manager.session.original_query == "first query"


# Helper Function Tests


def test_get_agent_tool_returns_classes() -> None:
    """Test get_agent_tool returns Agent and Tool classes."""
    agent_cls, tool_cls = get_agent_tool()

    assert agent_cls.__name__ == "Agent"
    assert tool_cls.__name__ == "Tool"


@pytest.mark.asyncio
async def test_check_query_satisfaction_always_returns_true() -> None:
    """Test check_query_satisfaction legacy compatibility."""
    mock_agent = Mock()
    mock_state = Mock()

    result = await check_query_satisfaction(
        agent=mock_agent,
        original_query="test query",
        response="test response",
        state_manager=mock_state,
    )

    assert result is True


# Integration Tests


@pytest.mark.asyncio
async def test_empty_response_handler_integration(state_manager: StateManager) -> None:
    """Integration test: EmptyResponseHandler tracks multiple cycles."""
    handler = EmptyResponseHandler(state_manager)

    # First empty response
    handler.track(is_empty=True)
    assert handler.should_intervene() is True

    # Simulate intervention
    with patch("tunacode.core.agents.main.ac.handle_empty_response", new_callable=AsyncMock):
        await handler.prompt_action("msg", "reason", 1)

    # Counter should reset
    assert handler.should_intervene() is False

    # New cycle
    handler.track(is_empty=True)
    assert handler.should_intervene() is True


def test_iteration_manager_productivity_cycle(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Integration test: IterationManager handles productivity cycles."""
    manager = IterationManager(state_manager, agent_config)
    response_state = Mock()
    response_state.task_completed = False

    # Productive iterations
    manager.track_productivity(had_tool_use=True, iteration=1)
    manager.track_productivity(had_tool_use=True, iteration=2)
    assert manager.unproductive_iterations == 0
    assert not manager.should_force_action(response_state)

    # Unproductive cycle
    manager.track_productivity(had_tool_use=False, iteration=3)
    manager.track_productivity(had_tool_use=False, iteration=4)
    manager.track_productivity(had_tool_use=False, iteration=5)
    assert manager.unproductive_iterations == 3
    assert manager.should_force_action(response_state)

    # Back to productive
    manager.track_productivity(had_tool_use=True, iteration=6)
    assert manager.unproductive_iterations == 0
    assert not manager.should_force_action(response_state)


@pytest.mark.asyncio
async def test_react_snapshot_manager_interval_and_limit(
    state_manager: StateManager, agent_config: AgentConfig
) -> None:
    """Integration test: ReactSnapshotManager respects interval and limits."""
    mock_tool = Mock()
    mock_tool.execute = AsyncMock()

    manager = ReactSnapshotManager(state_manager, mock_tool, agent_config)
    state_manager.session.react_scratchpad = {
        "timeline": [{"thoughts": "test", "next_action": "continue"}]
    }

    # Iteration 2: should snapshot
    assert manager.should_snapshot(2) is True
    await manager.capture_snapshot(2, None, False)
    assert state_manager.session.react_forced_calls == 1

    # Iteration 3: should not snapshot (not at interval)
    assert manager.should_snapshot(3) is False

    # Iteration 4: should snapshot
    assert manager.should_snapshot(4) is True
    await manager.capture_snapshot(4, None, False)
    assert state_manager.session.react_forced_calls == 2

    # Continue until limit (5 snapshots)
    await manager.capture_snapshot(6, None, False)
    await manager.capture_snapshot(8, None, False)
    await manager.capture_snapshot(10, None, False)
    assert state_manager.session.react_forced_calls == 5

    # Iteration 12: should not snapshot (limit reached)
    assert manager.should_snapshot(12) is False
