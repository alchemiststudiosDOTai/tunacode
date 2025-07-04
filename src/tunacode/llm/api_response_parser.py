"""
Module: tunacode.llm.api_response_parser
Provides a parser to standardize token usage information from various LLM API responses.
"""

from typing import Dict, Any
from tunacode.types import ModelName


class ApiResponseParser:
    """
    Parses LLM API responses from different providers to extract token usage.
    """

    def parse(self, model: ModelName, response: Dict[str, Any]) -> Dict[str, int]:
        """
        Parses the API response based on the provider.

        Args:
            provider (str): The name of the API provider (e.g., "openai", "anthropic").
            response (Dict[str, Any]): The raw dictionary response from the API.

        Returns:
            Dict[str, int]: A standardized dictionary with 'prompt_tokens' and
                            'completion_tokens'.
        """

        provider = model.split(":")[0]
        if provider == "openai":
            # print(self._parse_openai(response))
            return self._parse_openai(response)
        elif provider == "anthropic":
            return self._parse_anthropic(response)
        elif provider == "google-gla":
            return self._parse_google_gla(response)
        elif provider == "openrouter":
            return self._parse_openai(response)
        else:
            return {"prompt_tokens": 0, "completion_tokens": 0}

    def _parse_openai(self, response: Dict[str, Any]) -> Dict[str, int]:
        """Handles responses from OpenAI and compatible providers."""
        usage = response.get("usage", {})
        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }

    def _parse_anthropic(self, response: Dict[str, Any]) -> Dict[str, int]:
        """Handles responses from Anthropic's API."""
        usage = response.get("usage", {})
        return {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
        }

    def _parse_google_gla(self, response: Dict[str, Any]) -> Dict[str, int]:
        """Handles responses from Google's GLA (Gemini) API."""
        usage = response.get("usageMetadata", {})
        return {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
        }
