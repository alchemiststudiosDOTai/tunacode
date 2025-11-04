"""
Characterization tests for service initialization and lifecycle management (LLM and MCP).

Targets: src/tunacode/core/llm/__init__.py, src/tunacode/services/mcp.py
"""

import pytest


@pytest.mark.skip(
    reason="LLM service logic not present; lifecycle test will be implemented "
    "when logic is available."
)
def test_llm_service_initialization():
    """Should initialize LLM service and load configuration."""
    pass


@pytest.mark.skip(
    reason="MCP service logic not present; lifecycle test will be implemented "
    "when logic is available."
)
def test_mcp_service_initialization():
    """Should initialize MCP service and discover servers/tools."""
    pass


@pytest.mark.skip(
    reason="Service logic not present; shutdown/cleanup test will be implemented "
    "when logic is available."
)
def test_service_shutdown_cleanup():
    """Should clean up resources and shut down services gracefully."""
    pass
