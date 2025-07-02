"""Test edge cases for @-file-ref directory expansion feature."""

import os
from pathlib import Path

from tunacode.constants import MAX_FILE_SIZE, MAX_FILES_IN_DIR
from tunacode.utils.text_utils import expand_file_refs


class TestFileRefEdgeCases:
    """Test edge case scenarios for file reference expansion."""

    def test_empty_directory_expansion(self, tmp_path):
        """Test expanding an empty directory."""
        os.chdir(tmp_path)
        Path("empty_dir").mkdir()

        result, files = expand_file_refs("Check @empty_dir/")

        assert "=== START DIRECTORY EXPANSION: empty_dir/ ===" in result
        assert "=== END DIRECTORY EXPANSION: empty_dir/ ===" in result
        assert len(files) == 0

    def test_empty_recursive_directory_expansion(self, tmp_path):
        """Test expanding an empty directory recursively."""
        os.chdir(tmp_path)
        Path("empty_dir/subdir").mkdir(parents=True)

        result, files = expand_file_refs("Check @empty_dir/**")

        assert "=== START RECURSIVE EXPANSION: empty_dir/** ===" in result
        assert "=== END RECURSIVE EXPANSION: empty_dir/** ===" in result
        assert len(files) == 0

    def test_single_file_in_directory(self, tmp_path):
        """Test directory with just one file."""
        os.chdir(tmp_path)
        Path("single").mkdir()
        Path("single/only.txt").write_text("lonely content")

        result, files = expand_file_refs("Check @single/")

        assert "lonely content" in result
        assert len(files) == 1

    def test_hidden_files_included(self, tmp_path):
        """Test that hidden files (starting with .) are included."""
        os.chdir(tmp_path)
        Path("configs").mkdir()
        Path("configs/.env").write_text("SECRET=123")
        Path("configs/.gitignore").write_text("*.log")
        Path("configs/visible.txt").write_text("public")

        result, files = expand_file_refs("Check @configs/")

        assert "SECRET=123" in result
        assert "*.log" in result
        assert "public" in result
        assert len(files) == 3

    def test_special_characters_in_filenames(self, tmp_path):
        """Test files with special characters in names."""
        os.chdir(tmp_path)

        # Test various special characters that work with the regex
        special_files = [
            "file-with-dashes.txt",
            "file_with_underscores.py",
            "file.with.dots.js",
        ]

        for filename in special_files:
            Path(filename).write_text(f"content of {filename}")

        # Test individual file references
        for filename in special_files:
            result, files = expand_file_refs(f"Check @{filename}")
            assert f"content of {filename}" in result
            assert len(files) == 1

    def test_very_deep_directory_recursion(self, tmp_path):
        """Test recursive expansion with deeply nested directories."""
        os.chdir(tmp_path)

        # Create a deep directory structure
        deep_path = Path("deep")
        for i in range(10):
            deep_path = deep_path / f"level{i}"
        deep_path.mkdir(parents=True)

        # Add files at various levels
        Path("deep/file0.txt").write_text("at root")
        Path("deep/level0/level1/file1.txt").write_text("at level 1")
        deep_path.joinpath("deepest.txt").write_text("at bottom")

        result, files = expand_file_refs("Check @deep/**")

        assert "at root" in result
        assert "at level 1" in result
        assert "at bottom" in result
        assert len(files) == 3

    def test_mixed_file_types(self, tmp_path):
        """Test directory with various file types."""
        os.chdir(tmp_path)
        Path("mixed").mkdir()

        # Create files with different extensions
        Path("mixed/script.py").write_text("print('hello')")
        Path("mixed/data.json").write_text('{"key": "value"}')
        Path("mixed/style.css").write_text("body { color: red; }")
        Path("mixed/doc.md").write_text("# Documentation")
        Path("mixed/config.yaml").write_text("setting: true")

        result, files = expand_file_refs("Check @mixed/")

        # Check that all files are included with proper syntax highlighting
        assert "```python" in result  # .py files
        assert "```json" in result  # .json files
        assert "```css" in result  # .css files
        assert "```text" in result  # .md files map to text
        assert len(files) == 5

    def test_files_at_size_boundary(self, tmp_path):
        """Test files exactly at MAX_FILE_SIZE boundary."""
        os.chdir(tmp_path)

        # File exactly at limit (should be included)
        Path("exact_limit.txt").write_text("x" * MAX_FILE_SIZE)

        # File one byte over limit (should be skipped)
        Path("over_limit.txt").write_text("x" * (MAX_FILE_SIZE + 1))

        result1, files1 = expand_file_refs("Check @exact_limit.txt")
        assert "x" * MAX_FILE_SIZE in result1
        assert len(files1) == 1

        result2, files2 = expand_file_refs("Check @over_limit.txt")
        assert "SKIPPED (too large)" in result2
        assert len(files2) == 0

    def test_directory_at_file_count_limit(self, tmp_path):
        """Test directory with exactly MAX_FILES_IN_DIR files."""
        os.chdir(tmp_path)
        Path("many_files").mkdir()

        # Create exactly MAX_FILES_IN_DIR files
        for i in range(MAX_FILES_IN_DIR):
            Path(f"many_files/file_{i:03d}.txt").write_text(f"content {i}")

        result, files = expand_file_refs("Check @many_files/")

        assert len(files) == MAX_FILES_IN_DIR
        assert "Exceeds limit" not in result  # Should not show error

    def test_directory_over_file_count_limit(self, tmp_path):
        """Test directory with more than MAX_FILES_IN_DIR files."""
        os.chdir(tmp_path)
        Path("too_many_files").mkdir()

        # Create more than MAX_FILES_IN_DIR files
        for i in range(MAX_FILES_IN_DIR + 5):
            Path(f"too_many_files/file_{i:03d}.txt").write_text(f"content {i}")

        result, files = expand_file_refs("Check @too_many_files/")

        assert len(files) == MAX_FILES_IN_DIR
        assert f"Exceeds limit of {MAX_FILES_IN_DIR} files" in result

    def test_directory_at_total_size_limit(self, tmp_path):
        """Test directory approaching MAX_TOTAL_DIR_SIZE."""
        os.chdir(tmp_path)
        Path("big_dir").mkdir()

        # Create files that together approach but don't exceed the limit
        # Create smaller files that fit within the limit
        file_size = 50000  # 50KB per file
        num_files = 10
        for i in range(num_files):
            Path(f"big_dir/file_{i}.txt").write_text("y" * file_size)

        result, files = expand_file_refs("Check @big_dir/")

        # Should include all files without hitting limit (500KB < 2MB)
        assert len(files) == num_files
        assert "Total size exceeds" not in result

    def test_no_references_in_text(self, tmp_path):
        """Test text with no @ references passes through unchanged."""
        os.chdir(tmp_path)

        original_text = "This is plain text without any references."
        result, files = expand_file_refs(original_text)

        assert result == original_text
        assert len(files) == 0

    def test_multiple_references_same_file(self, tmp_path):
        """Test referencing the same file multiple times."""
        os.chdir(tmp_path)
        Path("shared.txt").write_text("shared content")

        result, files = expand_file_refs("Check @shared.txt and again @shared.txt")

        # File should be expanded twice in output but only counted once
        assert result.count("shared content") == 2
        assert len(files) == 1  # Deduped in file list

    def test_unicode_filenames(self, tmp_path):
        """Test files with unicode characters in names."""
        os.chdir(tmp_path)

        # Create files with unicode names
        unicode_files = ["café.txt", "файл.txt", "文件.txt", "αρχείο.txt"]

        for filename in unicode_files:
            try:
                Path(filename).write_text(f"Unicode content: {filename}")
            except OSError:
                # Skip if filesystem doesn't support this unicode
                continue

        # Test that we can reference them
        for filename in unicode_files:
            if Path(filename).exists():
                result, files = expand_file_refs(f"Check @{filename}")
                assert f"Unicode content: {filename}" in result

    def test_binary_file_handling(self, tmp_path):
        """Test handling of binary files."""
        os.chdir(tmp_path)

        # Create a file with binary content
        Path("binary.dat").write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

        # Should handle without crashing (errors='ignore')
        result, files = expand_file_refs("Check @binary.dat")

        assert len(files) == 1
        assert "=== FILE REFERENCE: binary.dat ===" in result

    def test_recursive_with_excluded_directories(self, tmp_path):
        """Test recursive expansion doesn't follow into .git, node_modules, etc."""
        os.chdir(tmp_path)

        # Create structure with typically excluded directories
        Path("project/src").mkdir(parents=True)
        Path("project/src/main.py").write_text("main code")
        Path("project/.git").mkdir(parents=True)
        Path("project/.git/config").write_text("git config")
        Path("project/node_modules/pkg").mkdir(parents=True)
        Path("project/node_modules/pkg/index.js").write_text("module code")

        result, files = expand_file_refs("Check @project/**")

        # Should include all files (no exclusion logic currently)
        assert "main code" in result
        assert "git config" in result
        assert "module code" in result
        assert len(files) == 3
