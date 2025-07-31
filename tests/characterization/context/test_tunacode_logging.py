"""Test TUNACODE.md logging when thoughts are enabled."""

import os
import tempfile
from pathlib import Path

import pytest

from tunacode.core.agents.main import get_or_create_agent
from tunacode.core.state import StateManager


@pytest.mark.asyncio
async def test_tunacode_loading_message_displayed(caplog):
    """Test that TUNACODE.md loading message is displayed when found."""
    # Create a temporary directory with TUNACODE.md
    with tempfile.TemporaryDirectory() as tmpdir:
        tunacode_path = Path(tmpdir) / "TUNACODE.md"
        tunacode_content = """# TUNACODE.md

This file provides guidance to AI assistants.

## Build Commands
- Run tests: `make test`
- Run single test: `pytest tests/test_file.py::test_name`
- Lint: `make lint`

## Code Style
- Use type hints for all functions
- Follow PEP 8 conventions
- Prefer guard clauses over nested conditionals
"""
        tunacode_path.write_text(tunacode_content)

        # Change to temp directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Create state manager with thoughts enabled
            state_manager = StateManager()
            state_manager.session.show_thoughts = True

            # Create agent (this should log the message)
            get_or_create_agent("openai:gpt-4", state_manager)

            # Check the log messages
            assert "📄 TUNACODE.md located: Loading context..." in caplog.text

        finally:
            os.chdir(original_cwd)


@pytest.mark.asyncio
async def test_tunacode_not_found_message(caplog):
    """Test that TUNACODE.md not found message is displayed when file doesn't exist."""
    # Create a temporary directory WITHOUT TUNACODE.md
    with tempfile.TemporaryDirectory() as tmpdir:
        # Change to temp directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Create state manager
            state_manager = StateManager()

            # Create agent (should log not found message)
            get_or_create_agent("openai:gpt-4", state_manager)

            # Check the log messages
            assert "📄 TUNACODE.md not found: Using default context" in caplog.text

        finally:
            os.chdir(original_cwd)
