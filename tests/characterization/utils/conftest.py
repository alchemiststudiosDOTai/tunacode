"""Configuration for characterization tests of utils."""

import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture(autouse=True)
def mock_genai_client():
    """Mocks the genai.Client for all tests in this directory."""
    with patch("tunacode.utils.token_counter.genai.Client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        
        def mock_count_tokens(model, contents):
            text = contents[0] if contents else ""
            return MagicMock(total_tokens=len(text))

        mock_instance.models.count_tokens.side_effect = mock_count_tokens
        yield mock_client
