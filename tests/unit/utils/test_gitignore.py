"""Tests for tunacode.utils.system.gitignore."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from tunacode.utils.system.gitignore import _load_gitignore_patterns, list_cwd


@pytest.fixture
def in_tmp_dir(tmp_path: Path):
    """Switch cwd to tmp_path for the duration of the test."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(original_cwd)


class TestLoadGitignorePatterns:
    def test_loads_patterns_from_file(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\nnode_modules/\n# comment\n\n__pycache__/\n")

        patterns = _load_gitignore_patterns(str(gitignore))
        assert patterns is not None
        assert "*.pyc" in patterns
        assert "node_modules/" in patterns
        assert "__pycache__/" in patterns
        assert "# comment" not in patterns
        assert "" not in patterns

    def test_always_includes_git_dir(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")
        patterns = _load_gitignore_patterns(str(gitignore))
        assert patterns is not None
        assert ".git/" in patterns

    def test_returns_none_for_missing_file(self):
        result = _load_gitignore_patterns("/nonexistent/.gitignore")
        assert result is None

    def test_returns_none_on_read_error(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("content")
        with patch("builtins.open", side_effect=OSError("read error")):
            result = _load_gitignore_patterns(str(gitignore))
            assert result is None


class TestListCwd:
    def test_lists_files_in_directory(self, in_tmp_dir):
        (in_tmp_dir / "file1.py").write_text("a")
        (in_tmp_dir / "file2.txt").write_text("b")
        sub = in_tmp_dir / "sub"
        sub.mkdir()
        (sub / "file3.py").write_text("c")

        result = list_cwd(max_depth=3)
        assert isinstance(result, list)
        assert result == sorted(result)
        assert "file1.py" in result
        assert "file2.txt" in result
        assert "sub/file3.py" in result

    def test_max_depth_zero_only_top_level(self, in_tmp_dir):
        (in_tmp_dir / "top.py").write_text("a")
        sub = in_tmp_dir / "sub"
        sub.mkdir()
        (sub / "nested.py").write_text("b")

        result = list_cwd(max_depth=0)
        for f in result:
            assert "/" not in f, f"Expected no nested files, got: {f}"

    def test_returns_sorted_list(self, in_tmp_dir):
        (in_tmp_dir / "b.txt").write_text("")
        (in_tmp_dir / "a.txt").write_text("")

        result = list_cwd(max_depth=0)
        assert result == sorted(result)

    def test_negative_depth_treated_as_zero(self, in_tmp_dir):
        (in_tmp_dir / "file.txt").write_text("")
        sub = in_tmp_dir / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("")

        result = list_cwd(max_depth=-1)
        assert "file.txt" in result
        for f in result:
            assert "/" not in f
