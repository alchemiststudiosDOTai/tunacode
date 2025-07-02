"""Test error handling for @-file-ref directory expansion feature."""

import os
from pathlib import Path

import pytest

from tunacode.utils.text_utils import expand_file_refs


class TestFileRefErrorHandling:
    """Test error handling scenarios for file reference expansion."""

    def test_nonexistent_file_raises_error(self, tmp_path):
        """Test that referencing a non-existent file raises ValueError."""
        os.chdir(tmp_path)

        with pytest.raises(ValueError) as exc_info:
            expand_file_refs("Check @nonexistent.txt")

        assert "Error: File not found at 'nonexistent.txt'" in str(exc_info.value)

    def test_nonexistent_directory_raises_error(self, tmp_path):
        """Test that referencing a non-existent directory raises ValueError."""
        os.chdir(tmp_path)

        with pytest.raises(ValueError) as exc_info:
            expand_file_refs("Check @missing_dir/")

        assert "Error: File not found at 'missing_dir'" in str(exc_info.value)

    def test_nonexistent_recursive_directory_raises_error(self, tmp_path):
        """Test that referencing a non-existent directory recursively raises ValueError."""
        os.chdir(tmp_path)

        with pytest.raises(ValueError) as exc_info:
            expand_file_refs("Check @missing_dir/**")

        assert "Error: File not found at 'missing_dir'" in str(exc_info.value)

    def test_file_referenced_as_directory_raises_error(self, tmp_path):
        """Test that using directory syntax on a file raises ValueError."""
        os.chdir(tmp_path)
        Path("regular_file.txt").write_text("content")

        with pytest.raises(ValueError) as exc_info:
            expand_file_refs("Check @regular_file.txt/")

        assert "Path 'regular_file.txt' for directory expansion is not a directory" in str(
            exc_info.value
        )

    def test_file_referenced_as_recursive_directory_raises_error(self, tmp_path):
        """Test that using recursive directory syntax on a file raises ValueError."""
        os.chdir(tmp_path)
        Path("regular_file.txt").write_text("content")

        with pytest.raises(ValueError) as exc_info:
            expand_file_refs("Check @regular_file.txt/**")

        assert "Path 'regular_file.txt' for recursive expansion is not a directory" in str(
            exc_info.value
        )

    def test_directory_without_trailing_slash_raises_error(self, tmp_path):
        """Test that referencing a directory without trailing slash raises helpful error."""
        os.chdir(tmp_path)
        Path("my_dir").mkdir()

        with pytest.raises(ValueError) as exc_info:
            expand_file_refs("Check @my_dir")

        assert "Path 'my_dir' is a directory" in str(exc_info.value)
        assert "Use 'my_dir/' for non-recursive" in str(exc_info.value)
        assert "'my_dir/**' for recursive" in str(exc_info.value)

    def test_invalid_path_characters(self, tmp_path):
        """Test handling of invalid path characters."""
        os.chdir(tmp_path)

        # Test with path containing null bytes or other invalid chars
        with pytest.raises(ValueError) as exc_info:
            expand_file_refs("Check @path\x00with\x00nulls.txt")

        assert "Error: File not found" in str(exc_info.value)

    def test_permission_denied_handling(self, tmp_path):
        """Test handling when file permissions prevent reading."""
        os.chdir(tmp_path)

        # Create a file and remove read permissions
        restricted_file = Path("restricted.txt")
        restricted_file.write_text("secret content")
        restricted_file.chmod(0o000)

        try:
            # This should handle the permission error gracefully
            with pytest.raises(PermissionError):
                expand_file_refs("Check @restricted.txt")
        finally:
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)

    def test_circular_symlink_handling(self, tmp_path):
        """Test handling of circular symbolic links."""
        os.chdir(tmp_path)

        try:
            # Create circular symlinks
            Path("link1").symlink_to("link2")
            Path("link2").symlink_to("link1")

            # This should raise ValueError as the file doesn't exist
            with pytest.raises(ValueError) as exc_info:
                expand_file_refs("Check @link1")

            assert "Error: File not found" in str(exc_info.value)
        except OSError:
            # Skip test if symlinks not supported
            pytest.skip("Symlinks not supported on this system")

    def test_broken_symlink_handling(self, tmp_path):
        """Test handling of broken symbolic links."""
        os.chdir(tmp_path)

        try:
            # Create a broken symlink
            Path("broken_link").symlink_to("nonexistent_target")

            with pytest.raises(ValueError) as exc_info:
                expand_file_refs("Check @broken_link")

            assert "Error: File not found" in str(exc_info.value)
        except OSError:
            # Skip test if symlinks not supported
            pytest.skip("Symlinks not supported on this system")

    def test_empty_reference_handling(self, tmp_path):
        """Test handling of empty @ references."""
        os.chdir(tmp_path)

        # The regex shouldn't match just @ without a path
        text = "Check @ without path"
        result, files = expand_file_refs(text)

        assert result == text  # Should remain unchanged
        assert len(files) == 0

    def test_multiple_errors_in_one_text(self, tmp_path):
        """Test that first error is reported when multiple references have issues."""
        os.chdir(tmp_path)
        Path("exists.txt").write_text("content")

        # First reference is valid, second is not
        with pytest.raises(ValueError) as exc_info:
            expand_file_refs("Check @exists.txt and @missing.txt")

        assert "Error: File not found at 'missing.txt'" in str(exc_info.value)
