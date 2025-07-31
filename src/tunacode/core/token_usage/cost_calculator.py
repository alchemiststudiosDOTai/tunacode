"""
Module: tunacode.pricing.cost_calculator
Provides a utility for calculating the cost of model usage based on token counts.
"""

from tunacode.configuration.models import ModelRegistry
from tunacode.types import CostAmount, ModelName, TokenCount


class CostCalculator:
    """
    Calculates the cost of a model interaction based on prompt and completion tokens.
    """

    def __init__(self, registry: ModelRegistry):
        """
        Initializes the CostCalculator with a model registry.

        Args:
            registry (ModelRegistry): An instance of ModelRegistry that contains
                                      the pricing information for various models.
        """
        self._registry = registry

    def calculate_cost(
        self,
        model_name: ModelName,
        prompt_tokens: TokenCount,
        completion_tokens: TokenCount,
    ) -> CostAmount:
        """
        Calculates the total cost for a given model and token usage.

        Args:
            model_name (ModelName): The identifier for the model (e.g., "openai:gpt-4o").
            prompt_tokens (TokenCount): The number of tokens in the input/prompt.
            completion_tokens (TokenCount): The number of tokens in the output/completion.

        Returns:
            CostAmount: The calculated cost as a float. Returns 0.0 if the model
                        is not found in the registry.
        """
        model_config = self._registry.get_model(model_name)

        if not model_config:
            return 0.0

        TOKENS_PER_MILLION = 1_000_000

        pricing = model_config.pricing

        # Safety check for None pricing
        if not pricing:
            return 0.0

        # Safety check for None pricing attributes
        if pricing.input is None or pricing.output is None:
            return 0.0

        input_cost = (prompt_tokens / TOKENS_PER_MILLION) * pricing.input

        output_cost = (completion_tokens / TOKENS_PER_MILLION) * pricing.output

        total_cost = input_cost + output_cost

        return total_cost
