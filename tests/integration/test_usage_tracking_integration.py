"""
Integration test for usage tracking.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from tunacode.core.agents.main import process_request
from tunacode.core.state import StateManager, SessionState
from tunacode.llm.api_response_parser import ApiResponseParser
from tunacode.pricing.cost_calculator import CostCalculator
from tunacode.types import ModelName


@pytest.mark.asyncio
async def test_usage_tracking_integration(monkeypatch):
    """
    Test that usage tracking is correctly integrated into the agent loop.
    """
    # 1. Create a mock StateManager instance
    mock_state_manager = MagicMock(spec=StateManager)
    mock_state_manager.session = SessionState()

    # 2. Mock the ApiResponseParser and CostCalculator
    mock_parser = MagicMock(spec=ApiResponseParser)
    mock_parser.parse.return_value = {"prompt_tokens": 100, "completion_tokens": 50}

    mock_calculator = MagicMock(spec=CostCalculator)
    mock_calculator.calculate_cost.return_value = 0.0015

    monkeypatch.setattr("tunacode.core.agents.main.ApiResponseParser", lambda: mock_parser)
    monkeypatch.setattr("tunacode.core.agents.main.CostCalculator", lambda: mock_calculator)

    # 3. Simulate a full agent processing cycle
    mock_agent = MagicMock()
    mock_agent.iter.return_value = AsyncMock()
    mock_agent.iter.return_value.__aenter__.return_value = AsyncMock()
    mock_agent.iter.return_value.__aenter__.return_value.__aiter__.return_value = [
        MagicMock(model_response={"usage": {"prompt_tokens": 100, "completion_tokens": 50}})
    ]

    async def mock_get_agent(*args, **kwargs):
        return mock_agent

    monkeypatch.setattr("tunacode.core.agents.main.get_or_create_agent", mock_get_agent)

    # Run the process_request function
    await process_request(
        model=ModelName("openai:gpt-4o"),
        message="test message",
        state_manager=mock_state_manager,
    )

    # 4. Assert that the session object contains the correct, updated values
    assert mock_state_manager.session.last_call_usage == {"prompt": 100, "completion": 50, "cost": 0.0015}
    assert mock_state_manager.session.session_total_usage == {"prompt": 100, "completion": 50, "cost": 0.0015}