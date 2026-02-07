"""Tests for tunacode.configuration.ignore_patterns."""

from tunacode.configuration.ignore_patterns import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_IGNORE_PATTERNS,
    GIT_DIR_PATTERN,
    _extract_exclude_dirs,
    _is_literal_dir_pattern,
    _matches_component_pattern,
    _matches_rooted_pattern,
    _matches_single_pattern,
    is_ignored,
)


class TestIsLiteralDirPattern:
    def test_simple_dir_pattern(self):
        assert _is_literal_dir_pattern("node_modules/") is True

    def test_wildcard_dir_pattern(self):
        assert _is_literal_dir_pattern("*.egg-info/") is False

    def test_file_pattern(self):
        assert _is_literal_dir_pattern("*.pyc") is False

    def test_no_slash(self):
        assert _is_literal_dir_pattern("node_modules") is False


class TestExtractExcludeDirs:
    def test_extracts_dirs(self):
        patterns = ["node_modules/", "*.pyc", ".venv/", "build/"]
        result = _extract_exclude_dirs(patterns)
        assert "node_modules" in result
        assert ".venv" in result
        assert "build" in result
        assert "*.pyc" not in result

    def test_empty(self):
        assert _extract_exclude_dirs([]) == frozenset()


class TestMatchesRootedPattern:
    def test_matches_exact(self):
        assert _matches_rooted_pattern("build", "build", is_dir_pattern=False) is True

    def test_matches_child(self):
        assert _matches_rooted_pattern("build/output", "build", is_dir_pattern=False) is True

    def test_dir_pattern_checks_prefix(self):
        assert _matches_rooted_pattern("build", "build", is_dir_pattern=True) is True
        assert _matches_rooted_pattern("build/out", "build", is_dir_pattern=True) is True

    def test_no_match(self):
        assert _matches_rooted_pattern("src", "build", is_dir_pattern=False) is False


class TestMatchesComponentPattern:
    def test_matches_component(self):
        assert (
            _matches_component_pattern(
                ["src", "node_modules", "pkg"],
                "pkg",
                "node_modules",
                is_dir_pattern=True,
                pattern="node_modules/",
            )
            is True
        )

    def test_file_pattern_with_slash_returns_false(self):
        assert (
            _matches_component_pattern(
                ["src", "file.py"],
                "file.py",
                "src/file.py",
                is_dir_pattern=False,
                pattern="src/file.py",
            )
            is False
        )

    def test_name_match_at_end(self):
        assert (
            _matches_component_pattern(
                ["file.pyc"], "file.pyc", "*.pyc", is_dir_pattern=False, pattern="*.pyc"
            )
            is True
        )


class TestMatchesSinglePattern:
    def test_rooted_pattern(self):
        assert _matches_single_pattern("build", "build", ["build"], "/build") is True

    def test_name_match(self):
        assert _matches_single_pattern("file.pyc", "file.pyc", ["file.pyc"], "*.pyc") is True

    def test_path_match(self):
        result = _matches_single_pattern(
            "src/file.pyc",
            "file.pyc",
            ["src", "file.pyc"],
            "*.pyc",
        )
        assert result is True

    def test_dir_pattern(self):
        assert (
            _matches_single_pattern(
                "node_modules", "node_modules", ["node_modules"], "node_modules/"
            )
            is True
        )


class TestIsIgnored:
    def test_git_dir_name(self):
        # .git is caught by the git check, but only when patterns is non-empty
        assert is_ignored(".git", ".git", [GIT_DIR_PATTERN]) is True

    def test_git_dir_path(self):
        assert is_ignored(".git/config", "config", [GIT_DIR_PATTERN]) is True

    def test_empty_patterns(self):
        assert is_ignored("file.py", "file.py", []) is False

    def test_empty_patterns_no_git_check(self):
        # When patterns is empty (falsy), function returns False immediately
        assert is_ignored(".git", ".git", []) is False

    def test_matches_pattern(self):
        assert is_ignored("file.pyc", "file.pyc", ["*.pyc"]) is True

    def test_no_match(self):
        assert is_ignored("file.py", "file.py", ["*.pyc"]) is False

    def test_nested_git_dir(self):
        assert is_ignored("subdir/.git/config", "config", [GIT_DIR_PATTERN]) is True

    def test_git_dir_caught_with_non_git_patterns(self):
        """When patterns is non-empty, .git is caught unconditionally."""
        assert is_ignored(".git", ".git", ["*.pyc"]) is True
        assert is_ignored(".git/config", "config", ["*.pyc"]) is True


class TestDefaultIgnorePatterns:
    def test_includes_common_dirs(self):
        assert "node_modules/" in DEFAULT_IGNORE_PATTERNS
        assert "__pycache__/" in DEFAULT_IGNORE_PATTERNS
        assert ".venv/" in DEFAULT_IGNORE_PATTERNS
        assert GIT_DIR_PATTERN in DEFAULT_IGNORE_PATTERNS

    def test_default_exclude_dirs_derived(self):
        assert "node_modules" in DEFAULT_EXCLUDE_DIRS
        assert "__pycache__" in DEFAULT_EXCLUDE_DIRS
        assert ".venv" in DEFAULT_EXCLUDE_DIRS
