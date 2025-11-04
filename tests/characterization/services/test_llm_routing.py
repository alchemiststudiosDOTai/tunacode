"""
Characterization tests for LLM routing, provider selection, and model validation.

Targets: src/tunacode/core/llm/__init__.py (and related LLM logic)
"""

import pytest


@pytest.mark.skip(
    reason="LLM service logic not present in src/tunacode/core/llm/__init__.py; "
            "test will be implemented when logic is available."
)
def test_llm_provider_selection():
    """Should select the correct LLM provider based on configuration."""
    pass


@pytest.mark.skip(
    reason="LLM service logic not present in src/tunacode/core/llm/__init__.py; "
            "test will be implemented when logic is available."
)
def test_llm_model_validation():
    """Should validate model names and raise errors for invalid models."""
    pass


@pytest.mark.skip(
    reason="LLM service logic not present in src/tunacode/core/llm/__init__.py; "
            "test will be implemented when logic is available."
)
def test_llm_routing_logic():
    """Should route requests to the correct LLM backend."""
    pass
