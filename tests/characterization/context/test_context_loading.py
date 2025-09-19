"""Unit tests for AGENTS.md context injection."""

import os
import tempfile
from pathlib import Path

import pytest

from tunacode.constants import GUIDE_FILE_NAME
from tunacode.context import (
    get_claude_files,
    get_code_style,
    get_directory_structure,
    get_git_status,
)
from tunacode.core.agents.agent_components import get_or_create_agent
from tunacode.core.state import StateManager


@pytest.mark.asyncio
async def test_get_code_style_walks_up_directory_tree():
    """Test that get_code_style looks for AGENTS.md up the directory tree."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create nested directories with AGENTS.md files
        root_dir = Path(tmpdir)
        sub_dir = root_dir / "subdir"
        sub_sub_dir = sub_dir / "subsubdir"

        sub_sub_dir.mkdir(parents=True)

        # Create AGENTS.md at different levels
        (root_dir / GUIDE_FILE_NAME).write_text("# Root context\nRoot level")
        (sub_dir / GUIDE_FILE_NAME).write_text("# Sub context\nSub level")

        # Change to deepest directory
        original_cwd = os.getcwd()
        try:
            os.chdir(sub_sub_dir)

            # Should concatenate both files
            style = await get_code_style()

            # Both contexts should be included (in reverse order - closest first)
            assert "Sub level" in style
            assert "Root level" in style

            # Verify order - sub should come before root
            assert style.index("Sub level") < style.index("Root level")

        finally:
            os.chdir(original_cwd)


@pytest.mark.asyncio
async def test_get_code_style_handles_empty_file():
    """Test that empty AGENTS.md files don't break loading."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_path = Path(tmpdir) / GUIDE_FILE_NAME
        agents_path.write_text("")  # Empty file

        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            style = await get_code_style()

            # Should return empty string for empty file
            assert style == ""

        finally:
            os.chdir(original_cwd)


@pytest.mark.asyncio
async def test_context_functions_return_all_types():
    """Test that context functions return git, directory, style, and files info."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create AGENTS.md
        agents_path = Path(tmpdir) / GUIDE_FILE_NAME
        agents_path.write_text("# Test context")

        # Create some files for directory structure
        (Path(tmpdir) / "src").mkdir()
        (Path(tmpdir) / "tests").mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Get all context components
            git = await get_git_status()
            directory = await get_directory_structure()
            style = await get_code_style()
            claude_files = await get_claude_files()

            # Should have all context types
            assert git is not None
            assert directory is not None
            assert style is not None
            assert claude_files is not None

            # Code style should contain our content
            assert "Test context" in style

        finally:
            os.chdir(original_cwd)


def test_agent_creation_with_large_agents_md():
    """Test that agent handles large AGENTS.md files gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a large AGENTS.md (10KB)
        large_content = "# Large Context\n\n" + ("x" * 80 + "\n") * 125
        agents_path = Path(tmpdir) / GUIDE_FILE_NAME
        agents_path.write_text(large_content)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Should not fail with large file
            state_manager = StateManager()
            agent = get_or_create_agent("openai:gpt-4", state_manager)

            assert agent is not None

        finally:
            os.chdir(original_cwd)


def test_agent_creation_with_malformed_agents_md():
    """Test that agent handles malformed AGENTS.md gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create AGENTS.md with potential encoding issues
        agents_path = Path(tmpdir) / GUIDE_FILE_NAME

        # Write binary data that might cause encoding issues
        with open(agents_path, "wb") as f:
            f.write(b"# Context\n\x80\x81\x82Invalid UTF-8")

        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Should not crash on malformed file
            state_manager = StateManager()
            agent = get_or_create_agent("openai:gpt-4", state_manager)

            assert agent is not None

        finally:
            os.chdir(original_cwd)
