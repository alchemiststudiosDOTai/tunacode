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
    # 1. ARRANGE
    model_name = "openai:gpt-4o"

    # --- FIX 1: The calculator needs the ENTIRE registry. ---
    registry = ModelRegistry()
    calculator = CostCalculator(registry)

    parser = ApiResponseParser()
    state_manager = StateManager()
    state_manager.session.current_model = model_name

    # --- FIX 2: Make the mock response behave like a dictionary for the parser. ---
    usage_dict = {"prompt_tokens": 1000, "completion_tokens": 2000}
    mock_response_object = MagicMock()
    mock_response_object.parts = []  # To prevent errors later in the function

    # Configure the .get() method to return the usage dictionary when called with "usage"
    mock_response_object.get.return_value = usage_dict

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


@pytest.mark.asyncio
async def test_session_total_accumulates_across_multiple_calls():
    """
    Tests that session_total_usage correctly accumulates token and cost
    data across multiple calls to _process_node.
    """
    # 1. ARRANGE: Set up components, same as the first test.
    model_name = "openai:gpt-4o"
    registry = ModelRegistry()
    calculator = CostCalculator(registry)
    parser = ApiResponseParser()
    state_manager = StateManager()
    state_manager.session.current_model = model_name

    # 2. ACT - FIRST CALL
    # Create the first mock node and its response
    usage_dict_1 = {"prompt_tokens": 1000, "completion_tokens": 2000}
    mock_response_1 = MagicMock()
    mock_response_1.parts = []
    mock_response_1.get.return_value = usage_dict_1
    mock_node_1 = MagicMock(model_response=mock_response_1, request=None, thought=None)

    await _process_node(
        node=mock_node_1,
        tool_callback=None,
        state_manager=state_manager,
        parser=parser,
        calculator=calculator,
    )

    # 3. ACT - SECOND CALL
    # Create a second mock node with different usage data
    usage_dict_2 = {"prompt_tokens": 500, "completion_tokens": 1500}
    mock_response_2 = MagicMock()
    mock_response_2.parts = []
    mock_response_2.get.return_value = usage_dict_2
    mock_node_2 = MagicMock(model_response=mock_response_2, request=None, thought=None)

    await _process_node(
        node=mock_node_2,
        tool_callback=None,
        state_manager=state_manager,
        parser=parser,
        calculator=calculator,
    )

    # 4. ASSERT
    # Assert the 'last_call_usage' reflects the SECOND call
    expected_cost_2 = 0.01625  # (500/1M * 2.5) + (1500/1M * 10)
    last_call = state_manager.session.last_call_usage
    assert last_call["prompt_tokens"] == 500
    assert last_call["completion_tokens"] == 1500
    assert last_call["cost"] == pytest.approx(expected_cost_2)

    # Assert the 'session_total_usage' reflects the SUM of BOTH calls
    expected_total_cost = 0.0225 + 0.01625  # cost_1 + cost_2
    session_total = state_manager.session.session_total_usage
    assert session_total["prompt_tokens"] == 1500  # 1000 + 500
    assert session_total["completion_tokens"] == 3500  # 2000 + 1500
    assert session_total["cost"] == pytest.approx(expected_total_cost)
