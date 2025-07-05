"""
Test suite for the ApiResponseParser.
"""

from types import SimpleNamespace
from tunacode.core.token_usage.api_response_parser import ApiResponseParser

# --- Arrange ---

# Mock a standardized response object that the parser expects.
# This simulates the output from pydantic-ai, regardless of the original provider.
mock_usage = SimpleNamespace(request_tokens=100, response_tokens=200)
mock_response_obj = SimpleNamespace(
    usage=mock_usage, model_name="provider:some-model-v1"
)


# --- Test Cases ---


def test_parse_successful_response():
    """
    Verifies that the parser correctly handles a standardized response object
    with all the expected usage and model name attributes.
    """
    # Arrange
    parser = ApiResponseParser()

    # Act
    # Pass the mock object to the parser
    result = parser.parse(mock_response_obj.model_name, mock_response_obj)

    # Assert
    # Check that the result includes the model_name and the correctly mapped tokens
    assert result == {
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "model_name": "provider:some-model-v1",
    }


def test_parse_response_with_no_usage_data():
    """
    Verifies that the parser returns a default, zeroed-out dictionary for tokens
    when the response object is missing the 'usage' attribute. This is important
    for graceful failure.
    """
    # Arrange
    parser = ApiResponseParser()
    # Create a mock object that is missing the .usage attribute
    mock_response_no_usage = SimpleNamespace(model_name="provider:model-without-usage")

    # Act
    result = parser.parse(mock_response_no_usage.model_name, mock_response_no_usage)

    # Assert
    assert result == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "model_name": "provider:model-without-usage",
    }


def test_parse_response_with_no_model_name():
    """
    Verifies that the parser falls back to the requested model name if the
    response object doesn't contain an explicit model name.
    """
    # Arrange
    parser = ApiResponseParser()
    requested_model_name = "requested:fallback-model"
    # Create a mock object that has usage but is missing the .model_name attribute
    mock_usage_only = SimpleNamespace(usage=mock_usage)

    # Act
    result = parser.parse(requested_model_name, mock_usage_only)

    # Assert
    assert result == {
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "model_name": requested_model_name,  # Should be the fallback name
    }
