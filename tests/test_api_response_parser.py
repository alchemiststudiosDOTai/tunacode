"""
Test suite for the ApiResponseParser.
"""
from tunacode.llm.api_response_parser import ApiResponseParser

# --- Arrange ---

# Mock API response for an OpenAI model
openai_model_name = "openai:gpt-4o"
openai_response = {
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 200
    }
}

# Mock API response for an Anthropic model
anthropic_model_name = "anthropic:claude-3-7-sonnet-latest"
anthropic_response = {
    "usage": {
        "input_tokens": 150,
        "output_tokens": 250
    }
}

# Mock API response for an OpenRouter model
openrouter_model_name = "openrouter:openai/gpt-4.1"
openrouter_response = {
    "usage": {
        "prompt_tokens": 120,
        "completion_tokens": 220
    }
}

# Mock API response for a Google GLA model
google_gla_model_name = "google-gla:gemini-2.0-flash"
google_gla_response = {
    "usageMetadata": {
        "promptTokenCount": 180,
        "candidatesTokenCount": 280
    }
}


# --- Test Cases ---

def get_provider_from_model_name(model_name: str) -> str:
    """Helper function to extract the provider from the model name string."""
    return model_name.split(':')[0]


def test_parse_openai_response():
    """
    Verifies that the parser correctly handles the OpenAI response format.
    """
    # Arrange
    parser = ApiResponseParser()
    provider = get_provider_from_model_name(openai_model_name)

    # Act
    result = parser.parse(provider, openai_response)

    # Assert
    assert result == {'prompt_tokens': 100, 'completion_tokens': 200}


def test_parse_anthropic_response():
    """
    Verifies that the parser correctly handles the Anthropic response format
    """
    # Arrange
    parser = ApiResponseParser()
    provider = get_provider_from_model_name(anthropic_model_name)

    # Act
    result = parser.parse(provider, anthropic_response)

    # Assert
    assert result == {'prompt_tokens': 150, 'completion_tokens': 250}


def test_parse_openrouter_response():
    """
    Verifies that the parser correctly handles the OpenRouter response format.
    """
    # Arrange
    parser = ApiResponseParser()
    provider = get_provider_from_model_name(openrouter_model_name)

    # Act
    result = parser.parse(provider, openrouter_response)

    # Assert
    assert result == {'prompt_tokens': 120, 'completion_tokens': 220}


def test_parse_google_gla_response():
    """
    Verifies that the parser correctly handles the Google GLA response format.
    """
    # Arrange
    parser = ApiResponseParser()
    provider = get_provider_from_model_name(google_gla_model_name)

    # Act
    result = parser.parse(provider, google_gla_response)

    # Assert
    assert result == {'prompt_tokens': 180, 'completion_tokens': 280}


def test_parse_unknown_provider_response():
    """
    Verifies that the parser returns a default, zeroed-out dictionary for
    any provider it doesn't recognize. This is important for graceful failure.
    """
    # Arrange
    parser = ApiResponseParser()

    # Act
    result = parser.parse("unknown_provider", {})

    # Assert
    assert result == {'prompt_tokens': 0, 'completion_tokens': 0}
