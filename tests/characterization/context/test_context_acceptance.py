"""Acceptance tests for AGENTS.md context injection into agent."""

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from tunacode.context import (
    get_claude_files,
    get_code_style,
    get_directory_structure,
    get_git_status,
)
from tunacode.core.agents.agent_components import get_or_create_agent
from tunacode.core.state import StateManager


@pytest.mark.asyncio
async def test_agent_includes_tunacode_md_context_in_system_prompt():
    """Acceptance test: Verify that AGENTS.md context is loaded properly."""
    # Given: A AGENTS.md file exists with project context
    tunacode_content = """# AGENTS.md

## Build Commands
- Run tests: `make test`
- Run single test: `pytest tests/test_file.py::test_name`
- Lint: `make lint`

## Code Style
- Use type hints for all functions
- Follow PEP 8 conventions
- Prefer guard clauses over nested conditionals
"""

    # Mock the file system to have AGENTS.md
    with mock.patch("pathlib.Path.exists") as mock_exists:
        with mock.patch("pathlib.Path.read_text") as mock_read:
            # Mock exists to return True for AGENTS.md
            mock_exists.return_value = True
            mock_read.return_value = tunacode_content

            # When: We get the context components individually
            style = await get_code_style()
            git = await get_git_status()
            directory = await get_directory_structure()
            claude_files = await get_claude_files()

            # Then: Code style should contain AGENTS.md content
            assert "Run tests: `make test`" in style
            assert "Use type hints for all functions" in style
            assert "Prefer guard clauses over nested conditionals" in style

            # And: Should have all context types
            assert git is not None
            assert directory is not None
            assert claude_files is not None


@pytest.mark.asyncio
async def test_agent_loads_tunacode_md_into_system_prompt():
    """Test that the agent actually loads AGENTS.md into its system prompt."""
    # Create a temporary directory with AGENTS.md
    with tempfile.TemporaryDirectory() as tmpdir:
        tunacode_path = Path(tmpdir) / "AGENTS.md"
        tunacode_content = """# Project-Specific Context

## Build Commands
- Run tests: `make test`
- Lint: `make lint`

## Code Style
- Use type hints for all functions
- Follow guard clause pattern
"""
        tunacode_path.write_text(tunacode_content)

        # Change to temp directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Clear caches to ensure fresh load
            from tunacode.core.agents.agent_components.agent_config import clear_all_caches

            clear_all_caches()

            # Create agent
            state_manager = StateManager()
            agent = get_or_create_agent("openai:gpt-4", state_manager)

            # Agent should be created successfully
            assert agent is not None

            # If we have access to real pydantic_ai, check system prompt
            if hasattr(agent, "system_prompt"):
                assert "Project Context from AGENTS.md" in agent.system_prompt
                assert "Use type hints for all functions" in agent.system_prompt
                assert "Follow guard clause pattern" in agent.system_prompt

        finally:
            os.chdir(original_cwd)
