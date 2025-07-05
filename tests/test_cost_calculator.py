from tunacode.configuration.models import ModelRegistry
from tunacode.core.token_usage.cost_calculator import CostCalculator


def test_calculate_cost_using_existing_registry():
    # ARRANGE
    # Use the actual ModelRegistry from the codebase
    registry = ModelRegistry()
    calculator = CostCalculator(registry)

    prompt_tokens = 1000
    completion_tokens = 2000
    model_name = "openai:gpt-4o"  # This model has input=2.50, output=10.00 per million

    # ACT
    # Cost = (1000/1M * $2.50) + (2000/1M * $10.00) = $0.0025 + $0.02 = $0.0225
    cost = calculator.calculate_cost(model_name, prompt_tokens, completion_tokens)

    # ASSERT
    assert cost == 0.0225


def test_calculate_cost_for_unknown_model_returns_zero():
    # ARRANGE
    registry = ModelRegistry()
    calculator = CostCalculator(registry)

    # ACT
    cost = calculator.calculate_cost("unknown:model-x", 1000, 1000)

    # ASSERT
    assert cost == 0.0
