import os
from pathlib import Path

import pytest

from tunacode.constants import (
    MAX_FILE_SIZE,
    MAX_FILES_IN_DIR,
    MAX_TOTAL_DIR_SIZE,
)
from tunacode.utils.text_utils import expand_file_refs


@pytest.fixture
def setup_test_environment(tmp_path: Path, request) -> Path:
    """
    Creates a temporary directory structure for testing.
    - /README.md
    - /src/main.py
    - /src/components/button.js
    - /src/components/style.css
    - /large_file.txt (exceeds MAX_FILE_SIZE)
    - /many_files_dir/ (contains more than MAX_FILES_IN_DIR files)
    - /empty_dir/
    """
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "empty_dir").mkdir()

    (tmp_path / "README.md").write_text("# Project Title")
    (tmp_path / "src/main.py").write_text("print('hello world')")
    (tmp_path / "src/components/button.js").write_text("export const Button = () => {};")
    (tmp_path / "src/components/style.css").write_text("button { color: blue; }")

    large_file_path = tmp_path / "large_file.txt"
    large_file_path.write_text("a" * (MAX_FILE_SIZE + 1))

    many_files_dir = tmp_path / "many_files_dir"
    many_files_dir.mkdir()
    for i in range(MAX_FILES_IN_DIR + 5):
        (many_files_dir / f"file_{i}.txt").write_text(f"content {i}")

    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    def finalizer():
        os.chdir(original_cwd)

    request.addfinalizer(finalizer)

    return tmp_path


def test_expand_single_file(setup_test_environment):
    """Tests expanding a single, valid @file reference."""
    text = "Please review this file: @README.md"
    expanded_text, file_list = expand_file_refs(text)

    assert "=== FILE REFERENCE: README.md ===" in expanded_text
    assert "# Project Title" in expanded_text
    assert len(file_list) == 1
    assert file_list[0] == str(Path("README.md").resolve())


def test_expand_non_recursive_directory(setup_test_environment):
    """Tests expanding a directory with a trailing slash (non-recursive)."""
    text = "What's in @src/ ?"
    expanded_text, file_list = expand_file_refs(text)

    assert "=== START DIRECTORY EXPANSION: src/ ===" in expanded_text
    assert "=== FILE REFERENCE: src/main.py ===" in expanded_text
    assert "print('hello world')" in expanded_text
    assert "=== FILE REFERENCE: src/components/button.js ===" not in expanded_text
    assert len(file_list) == 1
    assert str(Path("src/main.py").resolve()) in file_list


def test_expand_recursive_directory(setup_test_environment):
    """Tests expanding a directory recursively with /** syntax."""
    text = "Review the whole codebase: @src/**"
    expanded_text, file_list = expand_file_refs(text)

    assert "=== START RECURSIVE EXPANSION: src/** ===" in expanded_text
    assert "=== FILE REFERENCE: src/main.py ===" in expanded_text
    assert "=== FILE REFERENCE: src/components/button.js ===" in expanded_text
    assert "=== FILE REFERENCE: src/components/style.css ===" in expanded_text
    assert "export const Button" in expanded_text
    assert "button { color: blue; }" in expanded_text
    assert len(file_list) == 3


def test_no_references(setup_test_environment):
    """Tests that text without any @-references is returned unchanged."""
    text = "This is a normal sentence without any file references."
    expanded_text, file_list = expand_file_refs(text)

    assert expanded_text == text
    assert len(file_list) == 0


def test_multiple_mixed_references(setup_test_environment):
    """Tests a single prompt with both file and directory references."""
    text = "Check the readme @README.md and all the components in @src/components/"
    expanded_text, file_list = expand_file_refs(text)
    assert "=== FILE REFERENCE: README.md ===" in expanded_text
    assert "=== START DIRECTORY EXPANSION: src/components/ ===" in expanded_text
    assert "=== FILE REFERENCE: src/components/button.js ===" in expanded_text
    assert "=== FILE REFERENCE: src/components/style.css ===" in expanded_text
    assert len(file_list) == 3


def test_empty_directory(setup_test_environment):
    """Tests expanding an empty directory."""
    text = "What is in @empty_dir/ ?"
    expanded_text, file_list = expand_file_refs(text)

    assert "=== START DIRECTORY EXPANSION: empty_dir/ ===" in expanded_text
    assert "=== END DIRECTORY EXPANSION: empty_dir/ ===" in expanded_text
    assert "FILE REFERENCE" not in expanded_text.split("START DIRECTORY")[1]
    assert len(file_list) == 0


# --- Error and Limit Handling Tests ---


def test_error_path_not_found(setup_test_environment):
    """Tests that a ValueError is raised for a non-existent path."""
    text = "Here is a @nonexistent/file.py"
    with pytest.raises(ValueError) as excinfo:
        expand_file_refs(text)
    assert "Error: File not found" in str(excinfo.value)
    assert "nonexistent/file.py" in str(excinfo.value)


def test_error_path_is_file_but_used_as_dir(setup_test_environment):
    """Tests for ValueError when a file is referenced with directory syntax."""
    text = "This should fail: @README.md/"
    with pytest.raises(ValueError) as excinfo:
        expand_file_refs(text)
    assert "for directory expansion is not a directory" in str(excinfo.value)


def test_skip_file_too_large(setup_test_environment):
    """Tests that files exceeding MAX_FILE_SIZE are skipped."""
    text = "Check this huge file: @large_file.txt"
    expanded_text, file_list = expand_file_refs(text)

    assert "--- SKIPPED (too large): large_file.txt ---" in expanded_text
    assert "aaaaaaaa" not in expanded_text
    assert len(file_list) == 0


def test_limit_too_many_files_in_dir(setup_test_environment):
    """Tests that directory expansion stops after MAX_FILES_IN_DIR."""
    text = "Check this huge directory: @many_files_dir/"
    expanded_text, file_list = expand_file_refs(text)
    assert f"Exceeds limit of {MAX_FILES_IN_DIR} files" in expanded_text
    assert len(file_list) == MAX_FILES_IN_DIR


def test_limit_total_dir_size(tmp_path):
    """Tests that directory expansion stops if total size is exceeded."""
    size_test_dir = tmp_path / "size_test_dir"
    size_test_dir.mkdir()
    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    try:
        file_size = MAX_TOTAL_DIR_SIZE // 2 + 1000
        (size_test_dir / "file1.txt").write_text("b" * file_size)
        (size_test_dir / "file2.txt").write_text("c" * file_size)
        (size_test_dir / "file3.txt").write_text("d" * 10000)
        text = "Check this large content dir: @size_test_dir/"
        expanded_text, file_list = expand_file_refs(text)

        assert "SKIPPED (too large)" in expanded_text
        assert "FILE REFERENCE:" in expanded_text
        assert len(file_list) == 1
    finally:
        os.chdir(original_cwd)
