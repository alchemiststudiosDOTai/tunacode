"""
Test suite for the /init command that creates/updates AGENTS.md files.
Following strict TDD approach - acceptance test first.
"""

import os
import tempfile
from pathlib import Path

import pytest

from tunacode.cli.commands import CommandRegistry
from tunacode.constants import GUIDE_FILE_NAME
from tunacode.core.state import StateManager
from tunacode.types import CommandContext


@pytest.mark.asyncio
async def test_init_command_creates_agents_md_file():
    """Acceptance test: /init command should analyze codebase and create AGENTS.md file."""
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        os.chdir(tmpdir)

        try:
            # Create a minimal Python project structure
            Path("src").mkdir()
            Path("src/main.py").write_text("def hello(): return 'world'")
            Path("tests").mkdir()
            Path("tests/test_main.py").write_text("def test_hello(): assert True")
            Path("Makefile").write_text("test:\n\tpytest tests/")
            Path("pyproject.toml").write_text("[tool.black]\nline-length = 88")

            # Setup command registry and context
            registry = CommandRegistry()
            state_manager = StateManager()

            # Mock process_request to simulate agent creating the file
            async def mock_process_request(text, state_manager, output=True):
                # Simulate agent creating AGENTS.md
                Path(GUIDE_FILE_NAME).write_text("""# AGENTS.md

## Build/Test Commands
- Run tests: `make test`
- Run single test: `pytest tests/test_main.py::test_hello`

## Code Style
- Line length: 88 (Black)
- Follow PEP 8
""")

            context = CommandContext(
                state_manager=state_manager, process_request=mock_process_request
            )

            # Act
            await registry.execute("/init", context)

            # Assert
            assert Path(GUIDE_FILE_NAME).exists()
            content = Path(GUIDE_FILE_NAME).read_text()
            assert "make test" in content
            assert "pytest" in content
            assert "Code Style" in content

        finally:
            os.chdir(old_cwd)


@pytest.mark.asyncio
async def test_init_command_sends_correct_prompt():
    """Unit test: InitCommand should send the correct prompt to the agent."""
    # Arrange
    state_manager = StateManager()
    prompt_sent = None

    async def capture_prompt(text, state_manager, output=True):
        nonlocal prompt_sent
        prompt_sent = text

    context = CommandContext(state_manager=state_manager, process_request=capture_prompt)

    from tunacode.cli.commands import InitCommand

    command = InitCommand()

    # Act
    await command.execute([], context)

    # Assert
    assert prompt_sent is not None
    assert GUIDE_FILE_NAME in prompt_sent
    assert "Build/lint/test commands" in prompt_sent
    assert "Code style guidelines" in prompt_sent
    assert "20 lines long" in prompt_sent
    assert "Cursor rules" in prompt_sent


@pytest.mark.asyncio
async def test_init_command_matches_correct_names():
    """Unit test: InitCommand should match '/init' command."""
    # Arrange
    from tunacode.cli.commands import InitCommand

    command = InitCommand()

    # Assert
    assert command.name == "/init"
    assert command.aliases == []
    assert "AGENTS.md" in command.description


@pytest.mark.asyncio
async def test_init_command_improves_existing_agents_md():
    """Acceptance test: /init should improve existing AGENTS.md file."""
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        os.chdir(tmpdir)

        try:
            # Create existing AGENTS.md
            Path(GUIDE_FILE_NAME).write_text("# Old content\nSome basic info")

            # Create project files
            Path(".cursorrules").write_text("Always use type hints")

            # Setup command registry and context
            registry = CommandRegistry()
            state_manager = StateManager()

            # Mock process_request to simulate agent improving the file
            async def mock_process_request(text, state_manager, output=True):
                # Simulate agent improving AGENTS.md
                Path(GUIDE_FILE_NAME).write_text("""# AGENTS.md

## Build/Test Commands
- Run tests: `pytest`

## Code Style
- Always use type hints (from .cursorrules)
""")

            context = CommandContext(
                state_manager=state_manager, process_request=mock_process_request
            )

            # Act
            await registry.execute("/init", context)

            # Assert
            content = Path(GUIDE_FILE_NAME).read_text()
            assert "type hints" in content
            assert ".cursorrules" in content

        finally:
            os.chdir(old_cwd)


@pytest.mark.asyncio
async def test_init_command_sends_correct_prompt_duplicate():
    """Unit test: InitCommand should send the correct prompt to the agent."""
    # Arrange
    state_manager = StateManager()
    prompt_sent = None

    async def capture_prompt(text, state_manager, output=True):
        nonlocal prompt_sent
        prompt_sent = text

    context = CommandContext(state_manager=state_manager, process_request=capture_prompt)

    from tunacode.cli.commands import InitCommand

    command = InitCommand()

    # Act
    await command.execute([], context)

    # Assert
    assert prompt_sent is not None
    assert "AGENTS.md" in prompt_sent
    assert "Build/lint/test commands" in prompt_sent
    assert "Code style guidelines" in prompt_sent

    assert "20 lines long" in prompt_sent
    assert "Cursor rules" in prompt_sent


@pytest.mark.asyncio
async def test_init_command_matches_correct_names_duplicate():
    """Unit test: InitCommand should match '/init' command."""
    # Arrange
    from tunacode.cli.commands import InitCommand

    command = InitCommand()

    # Assert
    assert command.name == "/init"
    assert command.aliases == []
    assert "AGENTS.md" in command.description


@pytest.mark.asyncio
async def test_init_command_includes_cursor_rules_in_prompt():
    """Edge case: Prompt should mention looking for Cursor rules."""
    # Arrange
    state_manager = StateManager()
    prompt_sent = None

    async def capture_prompt(text, state_manager, output=True):
        nonlocal prompt_sent
        prompt_sent = text

    context = CommandContext(state_manager=state_manager, process_request=capture_prompt)

    from tunacode.cli.commands import InitCommand

    command = InitCommand()

    # Act
    await command.execute([], context)

    # Assert
    assert ".cursor/rules" in prompt_sent or ".cursorrules" in prompt_sent
    assert ".github/copilot-instructions.md" in prompt_sent


@pytest.mark.asyncio
async def test_init_command_returns_none():
    """Unit test: InitCommand should return None after execution."""
    # Arrange
    state_manager = StateManager()

    async def mock_process_request(text, state_manager, output=True):
        pass

    context = CommandContext(state_manager=state_manager, process_request=mock_process_request)

    from tunacode.cli.commands import InitCommand

    command = InitCommand()

    # Act
    result = await command.execute([], context)

    # Assert
    assert result is None
