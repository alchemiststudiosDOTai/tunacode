"""
Module: sidekick.utils.text_utils

Provides text processing utilities.
Includes file extension to language mapping and key formatting functions.
"""

import os
from typing import List, Set, Tuple


def key_to_title(key: str, uppercase_words: Set[str] = None) -> str:
    """Convert key to title, replacing underscores with spaces and capitalizing words."""
    if uppercase_words is None:
        uppercase_words = {"api", "id", "url"}

    words = key.split("_")
    result_words = []
    for word in words:
        lower_word = word.lower()
        if lower_word in uppercase_words:
            result_words.append(lower_word.upper())
        elif word:
            result_words.append(word[0].upper() + word[1:].lower())
        else:
            result_words.append("")

    return " ".join(result_words)


def ext_to_lang(path: str) -> str:
    """Get the language from the file extension. Default to `text` if not found."""
    MAP = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "java": "java",
        "c": "c",
        "cpp": "cpp",
        "cs": "csharp",
        "html": "html",
        "css": "css",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
    }
    ext = os.path.splitext(path)[1][1:]
    if ext in MAP:
        return MAP[ext]
    return "text"


def expand_file_refs(text: str) -> Tuple[str, List[str]]:
    """
    Expands @-references with file or directory contents wrapped in code fences.
    - @path/to/file.ext: Reads a single file.
    - @path/to/dir/: Reads all files in a directory (non-recursive).
    - @path/to/dir/**: Reads all files in a directory and its subdirectories.

    Args:
        text: The input text potentially containing @-references.

    Returns:
        A tuple containing:
            - Text with references replaced by file/directory contents.
            - List of absolute paths of files that were successfully expanded.

    Raises:
        ValueError: If a referenced path does not exist or if attempting to expand
                   TunaCode's own source directory.
    """
    import os
    import re
    from pathlib import Path

    from tunacode.constants import (
        ERROR_DIR_TOO_LARGE,
        ERROR_DIR_TOO_MANY_FILES,
        ERROR_FILE_NOT_FOUND,
        MAX_FILES_IN_DIR,
        MAX_TOTAL_DIR_SIZE,
    )

    # Regex now includes trailing / and ** to capture directory intentions
    pattern = re.compile(r"@([\w./\-_*]+)")
    expanded_files: list[str] = []

    def replacer(match: re.Match) -> str:
        path_spec = match.group(1)

        # Detect if we're expanding TunaCode's own src/ from TunaCode's repo
        # This prevents accidentally expanding TunaCode's source instead of user's project
        if path_spec.startswith("src/") or path_spec.startswith("src/**"):
            cwd = Path.cwd()
            tunacode_marker = cwd / "src" / "tunacode" / "__init__.py"
            if tunacode_marker.exists():
                raise ValueError(
                    "Error: TunaCode cannot expand file references when running "
                    "from its own source directory.\n"
                    "Please run TunaCode from your project directory, not from "
                    "the TunaCode repository itself.\n"
                    f"Current directory: {cwd}\n"
                    "Expected: Your project's root directory"
                )

        is_recursive = path_spec.endswith("/**")
        is_dir = path_spec.endswith("/")

        # Determine the actual path to check on the filesystem
        if is_recursive:
            base_path = path_spec[:-3]
        elif is_dir:
            base_path = path_spec[:-1]
        else:
            base_path = path_spec

        if not os.path.exists(base_path):
            raise ValueError(ERROR_FILE_NOT_FOUND.format(filepath=base_path))

        # For Recursive Directory Expansion ---
        if is_recursive:
            if not os.path.isdir(base_path):
                raise ValueError(
                    f"Error: Path '{base_path}' for recursive expansion is not a directory."
                )

            all_contents = [f"\n=== START RECURSIVE EXPANSION: {path_spec} ===\n"]
            total_size, file_count = 0, 0

            for root, _, filenames in os.walk(base_path):
                for filename in filenames:
                    if file_count >= MAX_FILES_IN_DIR:
                        all_contents.append(
                            ERROR_DIR_TOO_MANY_FILES.format(path=base_path, limit=MAX_FILES_IN_DIR)
                        )
                        break

                    file_path = os.path.join(root, filename)
                    content, size = _read_and_format_file(file_path, expanded_files)

                    if total_size + size > MAX_TOTAL_DIR_SIZE:
                        all_contents.append(
                            ERROR_DIR_TOO_LARGE.format(
                                path=base_path, limit_mb=MAX_TOTAL_DIR_SIZE / (1024 * 1024)
                            )
                        )
                        break

                    all_contents.append(content)
                    total_size += size
                    file_count += 1
                if file_count >= MAX_FILES_IN_DIR or total_size > MAX_TOTAL_DIR_SIZE:
                    break

            all_contents.append(f"\n=== END RECURSIVE EXPANSION: {path_spec} ===\n")
            return "".join(all_contents)

        # For Non-Recursive Directory Expansion
        if is_dir:
            if not os.path.isdir(base_path):
                raise ValueError(
                    f"Error: Path '{base_path}' for directory expansion is not a directory."
                )

            all_contents = [f"\n=== START DIRECTORY EXPANSION: {path_spec} ===\n"]
            total_size, file_count = 0, 0

            for item_name in sorted(os.listdir(base_path)):
                item_path = os.path.join(base_path, item_name)
                if os.path.isfile(item_path):
                    if file_count >= MAX_FILES_IN_DIR:
                        all_contents.append(
                            ERROR_DIR_TOO_MANY_FILES.format(path=base_path, limit=MAX_FILES_IN_DIR)
                        )
                        break

                    content, size = _read_and_format_file(item_path, expanded_files)
                    if total_size + size > MAX_TOTAL_DIR_SIZE:
                        all_contents.append(
                            ERROR_DIR_TOO_LARGE.format(
                                path=base_path, limit_mb=MAX_TOTAL_DIR_SIZE / (1024 * 1024)
                            )
                        )
                        break

                    all_contents.append(content)
                    total_size += size
                    file_count += 1

            all_contents.append(f"\n=== END DIRECTORY EXPANSION: {path_spec} ===\n")
            return "".join(all_contents)

        # For Single File Expansion
        if os.path.isfile(base_path):
            content, _ = _read_and_format_file(base_path, expanded_files)
            return content

        raise ValueError(f"Path '{base_path}' is not a valid file or directory specification.")

    expanded_text = pattern.sub(replacer, text)
    return expanded_text, list(set(expanded_files))


def _read_and_format_file(file_path: str, expanded_files_tracker: List[str]) -> Tuple[str, int]:
    """Reads a single file, formats it, and checks size limits."""
    from tunacode.constants import MAX_FILE_SIZE

    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        # Instead of raising an error, we'll just note it and skip or process gets terminated.
        return f"\n--- SKIPPED (too large): {file_path} ---\n", 0

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    abs_path = os.path.abspath(file_path)
    expanded_files_tracker.append(abs_path)

    lang = ext_to_lang(file_path)
    header = f"=== FILE REFERENCE: {file_path} ==="
    footer = f"=== END FILE REFERENCE: {file_path} ==="

    formatted_content = f"\n{header}\n```{lang}\n{content}\n```\n{footer}\n"
    return formatted_content, len(content.encode("utf-8"))
