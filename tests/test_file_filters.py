"""Tests for file filtering logic."""

from pathlib import Path

from tunacode.indexing.file_filters import (
    ALLOW_DOT_DIRS,
    IGNORE_DIR_SUFFIXES,
    IGNORE_DIRS,
    INDEXED_DOTFILES,
    INDEXED_EXTENSIONS,
    PRIORITY_DIRS,
    QUICK_INDEX_THRESHOLD,
    SPECIAL_FILENAMES,
    should_ignore_path,
    should_index_file,
)


class TestConstants:
    """Test that required constants are properly defined."""

    def test_ignore_dirs_exists(self) -> None:
        """IGNORE_DIRS should be a non-empty set."""
        assert isinstance(IGNORE_DIRS, set)
        assert len(IGNORE_DIRS) > 0
        assert ".git" in IGNORE_DIRS
        assert "node_modules" in IGNORE_DIRS

    def test_indexed_extensions_exists(self) -> None:
        """INDEXED_EXTENSIONS should be a non-empty set."""
        assert isinstance(INDEXED_EXTENSIONS, set)
        assert len(INDEXED_EXTENSIONS) > 0
        assert ".py" in INDEXED_EXTENSIONS
        assert ".js" in INDEXED_EXTENSIONS

    def test_priority_dirs_exists(self) -> None:
        """PRIORITY_DIRS should be a non-empty set."""
        assert isinstance(PRIORITY_DIRS, set)
        assert len(PRIORITY_DIRS) > 0
        assert "src" in PRIORITY_DIRS

    def test_quick_index_threshold(self) -> None:
        """QUICK_INDEX_THRESHOLD should be a positive integer."""
        assert isinstance(QUICK_INDEX_THRESHOLD, int)
        assert QUICK_INDEX_THRESHOLD > 0

    def test_allow_dot_dirs_exists(self) -> None:
        """ALLOW_DOT_DIRS should contain common allowed dot directories."""
        assert isinstance(ALLOW_DOT_DIRS, set)
        assert ".github" in ALLOW_DOT_DIRS
        assert ".vscode" in ALLOW_DOT_DIRS

    def test_ignore_dir_suffixes_exists(self) -> None:
        """IGNORE_DIR_SUFFIXES should contain directory suffixes to ignore."""
        assert isinstance(IGNORE_DIR_SUFFIXES, set)
        assert ".egg-info" in IGNORE_DIR_SUFFIXES

    def test_indexed_dotfiles_exists(self) -> None:
        """INDEXED_DOTFILES should contain indexable dotfiles."""
        assert isinstance(INDEXED_DOTFILES, set)
        assert ".gitignore" in INDEXED_DOTFILES
        assert ".dockerignore" in INDEXED_DOTFILES

    def test_special_filenames_exists(self) -> None:
        """SPECIAL_FILENAMES should contain special files without extensions."""
        assert isinstance(SPECIAL_FILENAMES, set)
        assert "makefile" in SPECIAL_FILENAMES
        assert "dockerfile" in SPECIAL_FILENAMES


class TestShouldIgnorePath:
    """Test path ignore logic."""

    def test_ignore_git_directory(self) -> None:
        """Should ignore .git directories."""
        path = Path("/repo/.git/config")
        assert should_ignore_path(path) is True

    def test_ignore_node_modules(self) -> None:
        """Should ignore node_modules directories."""
        path = Path("/repo/node_modules/package")
        assert should_ignore_path(path) is True

    def test_ignore_pycache(self) -> None:
        """Should ignore __pycache__ directories."""
        path = Path("/repo/src/__pycache__/module.pyc")
        assert should_ignore_path(path) is True

    def test_ignore_mypy_cache(self) -> None:
        """Should ignore .mypy_cache directories."""
        path = Path("/repo/.mypy_cache/file")
        assert should_ignore_path(path) is True

    def test_allow_github_directory(self) -> None:
        """Should NOT ignore .github directories (in allowlist)."""
        path = Path("/repo/.github/workflows/ci.yml")
        assert should_ignore_path(path) is False

    def test_allow_vscode_directory(self) -> None:
        """Should NOT ignore .vscode directories (in allowlist)."""
        path = Path("/repo/.vscode/settings.json")
        assert should_ignore_path(path) is False

    def test_allow_devcontainer_directory(self) -> None:
        """Should NOT ignore .devcontainer directories (in allowlist)."""
        path = Path("/repo/.devcontainer/devcontainer.json")
        assert should_ignore_path(path) is False

    def test_ignore_unlisted_dot_directory(self) -> None:
        """Should ignore dot directories not in allowlist."""
        path = Path("/repo/.secret/file.txt")
        assert should_ignore_path(path) is True

    def test_ignore_egg_info_suffix(self) -> None:
        """Should ignore directories ending with .egg-info."""
        path = Path("/repo/mypackage.egg-info/PKG-INFO")
        assert should_ignore_path(path) is True

    def test_allow_normal_directories(self) -> None:
        """Should not ignore normal directories."""
        path = Path("/repo/src/module/file.py")
        assert should_ignore_path(path) is False

    def test_allow_current_directory(self) -> None:
        """Should not ignore current directory (.)."""
        path = Path(".")
        assert should_ignore_path(path) is False


class TestShouldIndexFile:
    """Test file indexing decision logic."""

    def test_index_python_file(self, tmp_path: Path) -> None:
        """Should index Python files."""
        file_path = tmp_path / "test.py"
        file_path.write_text("print('hello')")
        assert should_index_file(file_path) is True

    def test_index_javascript_file(self, tmp_path: Path) -> None:
        """Should index JavaScript files."""
        file_path = tmp_path / "test.js"
        file_path.write_text("console.log('hello');")
        assert should_index_file(file_path) is True

    def test_index_markdown_file(self, tmp_path: Path) -> None:
        """Should index Markdown files."""
        file_path = tmp_path / "README.md"
        file_path.write_text("# Title")
        assert should_index_file(file_path) is True

    def test_ignore_unsupported_extension(self, tmp_path: Path) -> None:
        """Should not index files with unsupported extensions."""
        file_path = tmp_path / "test.xyz"
        file_path.write_text("content")
        assert should_index_file(file_path) is False

    def test_index_makefile_no_extension(self, tmp_path: Path) -> None:
        """Should index Makefile without extension."""
        file_path = tmp_path / "Makefile"
        file_path.write_text("all:\n\techo 'test'")
        assert should_index_file(file_path) is True

    def test_index_dockerfile_no_extension(self, tmp_path: Path) -> None:
        """Should index Dockerfile without extension."""
        file_path = tmp_path / "Dockerfile"
        file_path.write_text("FROM ubuntu")
        assert should_index_file(file_path) is True

    def test_index_shebang_script(self, tmp_path: Path) -> None:
        """Should index scripts with shebang."""
        file_path = tmp_path / "script"
        file_path.write_text("#!/bin/bash\necho 'test'")
        assert should_index_file(file_path) is True

    def test_ignore_large_files(self, tmp_path: Path) -> None:
        """Should not index very large files (>10MB)."""
        file_path = tmp_path / "large.py"
        file_path.write_bytes(b"x" * (11 * 1024 * 1024))
        assert should_index_file(file_path) is False

    def test_ignore_binary_without_extension(self, tmp_path: Path) -> None:
        """Should not index random binary files without extension."""
        file_path = tmp_path / "binary"
        file_path.write_bytes(b"\x00\x01\x02\x03")
        assert should_index_file(file_path) is False

    def test_handle_nonexistent_file(self) -> None:
        """Should handle nonexistent files gracefully."""
        file_path = Path("/nonexistent/file.py")
        assert should_index_file(file_path) is False

    def test_index_gitignore(self, tmp_path: Path) -> None:
        """Should index .gitignore files."""
        file_path = tmp_path / ".gitignore"
        file_path.write_text("*.pyc\n__pycache__/")
        assert should_index_file(file_path) is True

    def test_index_dockerignore(self, tmp_path: Path) -> None:
        """Should index .dockerignore files."""
        file_path = tmp_path / ".dockerignore"
        file_path.write_text("node_modules/")
        assert should_index_file(file_path) is True

    def test_index_editorconfig(self, tmp_path: Path) -> None:
        """Should index .editorconfig files."""
        file_path = tmp_path / ".editorconfig"
        file_path.write_text("root = true")
        assert should_index_file(file_path) is True

    def test_large_special_file_rejected(self, tmp_path: Path) -> None:
        """Should reject large special files (size check applied consistently)."""
        file_path = tmp_path / "Makefile"
        file_path.write_bytes(b"x" * (11 * 1024 * 1024))
        assert should_index_file(file_path) is False

    def test_large_shebang_file_rejected(self, tmp_path: Path) -> None:
        """Should reject large shebang files (size check applied consistently)."""
        file_path = tmp_path / "script"
        content = b"#!/bin/bash\n" + b"x" * (11 * 1024 * 1024)
        file_path.write_bytes(content)
        assert should_index_file(file_path) is False
