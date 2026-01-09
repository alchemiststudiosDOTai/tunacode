"""Tests for glob and grep path validation with ModelRetry.

These tests verify that glob and grep tools raise ModelRetry on bad paths,
enabling LLM self-correction instead of returning error strings.
"""

import pytest
from pydantic_ai.exceptions import ModelRetry


class TestGlobPathValidation:
    """Tests for glob tool path validation."""

    async def test_nonexistent_directory_raises_modelretry(self, tmp_path):
        """Glob with nonexistent directory raises ModelRetry."""
        from tunacode.tools.glob import glob

        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(ModelRetry) as exc_info:
            await glob(pattern="*.py", directory=str(nonexistent))

        assert (
            "not found" in str(exc_info.value).lower()
            or "does not exist" in str(exc_info.value).lower()
        )

    async def test_file_path_instead_of_directory_raises_modelretry(self, tmp_path):
        """Glob with file path (not directory) raises ModelRetry."""
        from tunacode.tools.glob import glob

        # Create a file, not a directory
        file_path = tmp_path / "some_file.txt"
        file_path.write_text("content")

        with pytest.raises(ModelRetry) as exc_info:
            await glob(pattern="*.py", directory=str(file_path))

        assert "not a directory" in str(exc_info.value).lower()


class TestGrepPathValidation:
    """Tests for grep tool path validation."""

    async def test_nonexistent_directory_raises_modelretry(self, tmp_path):
        """Grep with nonexistent directory raises ModelRetry."""
        from tunacode.tools.grep import grep

        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(ModelRetry) as exc_info:
            await grep(pattern="test", directory=str(nonexistent))

        assert (
            "not found" in str(exc_info.value).lower()
            or "does not exist" in str(exc_info.value).lower()
        )

    async def test_file_path_instead_of_directory_raises_modelretry(self, tmp_path):
        """Grep with file path (not directory) raises ModelRetry."""
        from tunacode.tools.grep import grep

        # Create a file, not a directory
        file_path = tmp_path / "some_file.txt"
        file_path.write_text("content")

        with pytest.raises(ModelRetry) as exc_info:
            await grep(pattern="test", directory=str(file_path))

        assert "not a directory" in str(exc_info.value).lower()
