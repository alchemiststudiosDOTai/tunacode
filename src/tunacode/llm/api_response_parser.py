"""
Module: tunacode.llm.api_response_parser
Provides a parser to standardize token usage information from various LLM API responses.
"""

from typing import Dict, Any
from tunacode.types import ModelName


class ApiResponseParser:
    """
    Parses LLM API response objects to extract token usage and the actual model name used.
    This version works directly with the pydantic-ai ModelResponse object.
    """

    def parse(self, model: ModelName, response_obj: Any) -> Dict[str, Any]:
        """
        Parses the standardized API response object.

        Args:
            model (ModelName): The model name that was requested. Used as a fallback.
            response_obj (Any): The raw ModelResponse object from the agent.

        Returns:
            Dict[str, Any]: A standardized dictionary with 'prompt_tokens',
                            'completion_tokens', and 'model_name'.
        """
        # --- FIX: Access attributes directly from the object ---
        # Default to an empty object if usage is None
        usage = getattr(response_obj, "usage", None) or {}

        # Extract the actual model name, falling back to the requested model.
        actual_model_name = getattr(response_obj, "model_name", model)

        # The pydantic-ai Usage object standardizes keys to 'request_tokens'
        # and 'response_tokens'. We access them as attributes.
        parsed_data = {
            "prompt_tokens": getattr(usage, "request_tokens", 0),
            "completion_tokens": getattr(usage, "response_tokens", 0),
            "model_name": actual_model_name,
        }

        return parsed_data
