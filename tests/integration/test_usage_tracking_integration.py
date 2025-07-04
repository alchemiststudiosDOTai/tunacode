import pytest
from unittest.mock import MagicMock

# Your actual, implemented components
from tunacode.core.agents.main import _process_node
from tunacode.core.state import StateManager
from tunacode.llm.api_response_parser import ApiResponseParser
from tunacode.pricing.cost_calculator import CostCalculator
from tunacode.configuration.models import ModelRegistry

@pytest.mark.asyncio
async def test_node_processing_updates_usage_state():
    """
    Tests that _process_node correctly integrates the parser, calculator,
    and state manager to track usage and cost after a model response.
    """
    # 1. ARRANGE: Set up the real components and a realistic state.
    # Since the parser and calculator are unit-tested, we can use them directly.
    model_name = "openai:gpt-4o"
    registry = ModelRegistry().get_model(name=model_name)
    calculator = CostCalculator(registry)
    parser = ApiResponseParser()
    state_manager = StateManager()
    state_manager.session.current_model = model_name

    # This is our only mock: a simplified "node" from the agent loop.
    # It just needs to hold the raw API response.
    mock_response_object = MagicMock()
    mock_response_object.usage = {"prompt_tokens": 1000, "completion_tokens": 2000}
    mock_response_object.parts = []

    mock_node = MagicMock()
    mock_node.model_response = mock_response_object
    mock_node.request = None
    mock_node.thought = None

    # 2. ACT: Call the specific function containing your integration logic.
    await _process_node(
        node=mock_node,
        tool_callback=None,
        state_manager=state_manager,
        parser=parser,
        calculator=calculator,
    )

    # 3. ASSERT: Check that the state was updated correctly.
    # Based on gpt-4o pricing of $5/M input and $15/M output:
    # Cost = (1000/1M * $2.50) + (2000/1M * $10.00) = $0.0025 + $0.02 = $0.0225
    expected_cost = 0.0225

    # Check the last call's data
    last_call = state_manager.session.last_call_usage
    assert last_call["prompt_tokens"] == 1000
    assert last_call["completion_tokens"] == 2000
    assert last_call["cost"] == pytest.approx(expected_cost)

    # Check the session total (which is just the first call)
    session_total = state_manager.session.session_total_usage
    assert session_total["prompt_tokens"] == 1000
    assert session_total["completion_tokens"] == 2000
    assert session_total["cost"] == pytest.approx(expected_cost)