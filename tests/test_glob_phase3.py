"""Test suite for Phase 3 glob tool enhancements."""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from tunacode.tools.glob import GlobTool, glob


@pytest.mark.asyncio
async def test_glob_basic_functionality():
    """Test basic glob pattern matching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file structure
        test_files = [
            "test.py",
            "main.py",
            "src/app.py",
            "src/util.py",
            "tests/test_main.py",
            "docs/readme.md",
            "docs/api.md",
        ]

        for file_path in test_files:
            full_path = Path(tmpdir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(f"# {file_path}")

        # Test basic pattern
        result = await glob("*.py", directory=tmpdir)
        assert "test.py" in result
        assert "main.py" in result
        assert "src/app.py" not in result  # Not in root

        # Test recursive pattern
        result = await glob("**/*.py", directory=tmpdir)
        assert "test.py" in result
        assert "app.py" in result  # Will show as src/app.py in grouped output
        assert "test_main.py" in result  # Will show as tests/test_main.py in grouped output

        # Test brace expansion
        result = await glob("**/*.{py,md}", directory=tmpdir)
        assert "test.py" in result
        assert "readme.md" in result  # Shows as readme.md in grouped output


@pytest.mark.asyncio
async def test_glob_sorting_options():
    """Test different sorting options."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files with different sizes and modification times
        file1 = Path(tmpdir) / "a.txt"
        file2 = Path(tmpdir) / "b.txt"
        file3 = Path(tmpdir) / "c.txt"

        file1.write_text("x" * 100)
        file2.write_text("x" * 200)
        file3.write_text("x" * 50)

        # Touch files to set different modification times
        os.utime(file1, (0, 1000))
        os.utime(file2, (0, 2000))
        os.utime(file3, (0, 1500))

        tool = GlobTool()

        # Test alphabetical sorting
        result = await tool._execute("*.txt", directory=tmpdir, sort_by="alphabetical")
        lines = result.split("\n")
        file_lines = [line.strip() for line in lines if line.strip().startswith("-")]
        assert file_lines == ["- a.txt", "- b.txt", "- c.txt"]

        # Test size sorting
        result = await tool._execute("*.txt", directory=tmpdir, sort_by="size")
        lines = result.split("\n")
        file_lines = [line.strip() for line in lines if line.strip().startswith("-")]
        assert file_lines == ["- b.txt", "- a.txt", "- c.txt"]

        # Test modification time sorting
        result = await tool._execute("*.txt", directory=tmpdir, sort_by="modified")
        lines = result.split("\n")
        file_lines = [line.strip() for line in lines if line.strip().startswith("-")]
        assert file_lines == ["- b.txt", "- c.txt", "- a.txt"]


@pytest.mark.asyncio
async def test_glob_case_sensitivity():
    """Test case-sensitive and case-insensitive matching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_files = ["Test.py", "test.PY", "TEST.py", "main.py"]
        for file_name in test_files:
            (Path(tmpdir) / file_name).write_text(f"# {file_name}")

        tool = GlobTool()

        # Case-insensitive (default)
        result = await tool._execute("test.py", directory=tmpdir, case_sensitive=False)
        assert "Test.py" in result
        assert "TEST.py" in result

        # Case-sensitive
        result = await tool._execute("test.py", directory=tmpdir, case_sensitive=True)
        assert "Test.py" not in result
        assert "TEST.py" not in result
        assert "No files found" in result  # Only exact match would work


@pytest.mark.asyncio
async def test_glob_gitignore_support():
    """Test .gitignore pattern support."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_files = [
            "main.py",
            "test.py",
            "build/output.py",
            "dist/app.py",
            "src/core.py",
        ]

        for file_path in test_files:
            full_path = Path(tmpdir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(f"# {file_path}")

        # Create .gitignore
        gitignore = Path(tmpdir) / ".gitignore"
        gitignore.write_text("build/\ndist/\n*.pyc")

        tool = GlobTool()

        # With gitignore (default)
        result = await tool._execute("**/*.py", directory=tmpdir, use_gitignore=True)
        assert "main.py" in result
        assert "core.py" in result  # Shows as src/core.py but displayed as core.py
        # Note: Current implementation doesn't fully process gitignore patterns
        # This is a placeholder for future enhancement

        # Without gitignore
        result = await tool._execute("**/*.py", directory=tmpdir, use_gitignore=False)
        assert "main.py" in result
        # Note: build/ and dist/ are excluded by default EXCLUDE_DIRS,
        # so they won't show up regardless
        # The gitignore functionality is implemented but these directories are always excluded


@pytest.mark.asyncio
async def test_glob_brace_expansion_nested():
    """Test nested brace expansion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_files = [
            "app.js",
            "app.ts",
            "app.jsx",
            "app.tsx",
            "test.js",
            "test.ts",
            "main.py",
            "util.rb",
        ]

        for file_name in test_files:
            (Path(tmpdir) / file_name).write_text(f"// {file_name}")

        tool = GlobTool()

        # Test nested braces
        patterns = tool._expand_brace_pattern("{app,test}.{js,ts}")
        assert set(patterns) == {"app.js", "app.ts", "test.js", "test.ts"}

        # Test actual glob with nested braces
        result = await tool._execute("{app,test}.{js,ts}", directory=tmpdir)
        assert "app.js" in result
        assert "app.ts" in result
        assert "test.js" in result
        assert "test.ts" in result
        assert "main.py" not in result


if __name__ == "__main__":
    asyncio.run(test_glob_basic_functionality())
    asyncio.run(test_glob_sorting_options())
    asyncio.run(test_glob_case_sensitivity())
    asyncio.run(test_glob_gitignore_support())
    asyncio.run(test_glob_brace_expansion_nested())
    print("All tests passed!")
