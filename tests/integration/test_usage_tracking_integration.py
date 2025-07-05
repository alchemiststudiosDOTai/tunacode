import pytest
from unittest.mock import MagicMock

# Your actual, implemented components
from tunacode.core.agents.main import _process_node
from tunacode.core.state import StateManager
from tunacode.core.token_usage.api_response_parser import ApiResponseParser
from tunacode.core.token_usage.cost_calculator import CostCalculator
from tunacode.configuration.models import ModelRegistry
# Import the new UsageTracker class
from tunacode.core.token_usage.usage_tracker import UsageTracker


@pytest.mark.asyncio
async def test_node_processing_updates_usage_state():
    """
    Tests that _process_node correctly uses the UsageTracker to update state.
    """
    # 1. ARRANGE
    model_name = "openai:gpt-4o"
    state_manager = StateManager()
    state_manager.session.current_model = model_name

    # --- FIX: Instantiate the UsageTracker with its dependencies ---
    parser = ApiResponseParser()
    registry = ModelRegistry()
    calculator = CostCalculator(registry)
    usage_tracker = UsageTracker(parser, calculator, state_manager)

    # Mock the response object with token values
    prompt_tokens = 1000
    completion_tokens = 2000
    mock_usage = MagicMock(request_tokens=prompt_tokens, response_tokens=completion_tokens)
    mock_response_object = MagicMock(
        usage=mock_usage, model_name=model_name, parts=[]
    )
    mock_node = MagicMock(model_response=mock_response_object, request=None, thought=None)

    # Calculate the expected cost dynamically using the ModelRegistry
    model_config = registry.get_model(model_name)
    input_price = model_config.pricing.input
    output_price = model_config.pricing.output
    expected_cost = (
        (prompt_tokens / 1_000_000) * input_price
    ) + ((completion_tokens / 1_000_000) * output_price)

    # 2. ACT
    # --- FIX: Pass the usage_tracker instance to _process_node ---
    await _process_node(
        node=mock_node,
        tool_callback=None,
        state_manager=state_manager,
        usage_tracker=usage_tracker,
    )

    # 3. ASSERT
    last_call = state_manager.session.last_call_usage
    assert last_call["prompt_tokens"] == prompt_tokens
    assert last_call["completion_tokens"] == completion_tokens
    assert last_call["cost"] == pytest.approx(expected_cost)

    session_total = state_manager.session.session_total_usage
    assert session_total["cost"] == pytest.approx(expected_cost)


@pytest.mark.asyncio
async def test_session_total_accumulates_across_multiple_calls():
    """
    Tests that the UsageTracker correctly accumulates totals across multiple calls.
    """
    # 1. ARRANGE
    model_name = "openai:gpt-4o"
    state_manager = StateManager()
    state_manager.session.current_model = model_name

    # --- FIX: Instantiate the UsageTracker once ---
    parser = ApiResponseParser()
    registry = ModelRegistry()
    calculator = CostCalculator(registry)
    usage_tracker = UsageTracker(parser, calculator, state_manager)

    # Calculate all expected costs dynamically
    model_config = registry.get_model(model_name)
    input_price = model_config.pricing.input
    output_price = model_config.pricing.output

    prompt_tokens_1, completion_tokens_1 = 1000, 2000
    prompt_tokens_2, completion_tokens_2 = 500, 1500

    expected_cost_1 = ((prompt_tokens_1 / 1_000_000) * input_price) + ((completion_tokens_1 / 1_000_000) * output_price)
    expected_cost_2 = ((prompt_tokens_2 / 1_000_000) * input_price) + ((completion_tokens_2 / 1_000_000) * output_price)
    expected_total_cost = expected_cost_1 + expected_cost_2

    # Mock the API responses
    mock_usage_1 = MagicMock(request_tokens=prompt_tokens_1, response_tokens=completion_tokens_1)
    mock_response_1 = MagicMock(usage=mock_usage_1, model_name=model_name, parts=[])
    mock_node_1 = MagicMock(model_response=mock_response_1, request=None, thought=None)

    mock_usage_2 = MagicMock(request_tokens=prompt_tokens_2, response_tokens=completion_tokens_2)
    mock_response_2 = MagicMock(usage=mock_usage_2, model_name=model_name, parts=[])
    mock_node_2 = MagicMock(model_response=mock_response_2, request=None, thought=None)

    # 2. ACT - FIRST CALL
    # --- FIX: Pass the same usage_tracker instance to both calls ---
    await _process_node(node=mock_node_1, tool_callback=None, state_manager=state_manager, usage_tracker=usage_tracker)

    # 3. ACT - SECOND CALL
    await _process_node(node=mock_node_2, tool_callback=None, state_manager=state_manager, usage_tracker=usage_tracker)

    # 4. ASSERT
    last_call = state_manager.session.last_call_usage
    assert last_call["prompt_tokens"] == prompt_tokens_2
    assert last_call["completion_tokens"] == completion_tokens_2
    assert last_call["cost"] == pytest.approx(expected_cost_2)

    session_total = state_manager.session.session_total_usage
    assert session_total["prompt_tokens"] == prompt_tokens_1 + prompt_tokens_2
    assert session_total["completion_tokens"] == completion_tokens_1 + completion_tokens_2
    assert session_total["cost"] == pytest.approx(expected_total_cost)