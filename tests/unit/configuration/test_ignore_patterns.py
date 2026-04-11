from __future__ import annotations

from pathlib import Path

from tunacode.configuration.ignore_patterns import (
    DEFAULT_IGNORE_PATTERNS,
    compile_ignore_spec,
    merge_ignore_patterns,
    read_ignore_file_lines,
)


def test_compile_ignore_spec_combines_defaults_and_gitignore_lines(tmp_path: Path) -> None:
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text("generated.txt\ncustom-output/\n", encoding="utf-8")

    patterns = merge_ignore_patterns(
        DEFAULT_IGNORE_PATTERNS, read_ignore_file_lines(gitignore_path)
    )
    spec = compile_ignore_spec(patterns)

    assert spec.match_file(".venv/lib/python3.11/site.py") is True
    assert spec.match_file("generated.txt") is True
    assert spec.match_file("custom-output/result.json") is True
    assert spec.match_file("src/app.py") is False


def test_read_ignore_file_lines_returns_empty_tuple_for_invalid_utf8(tmp_path: Path) -> None:
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_bytes(b"\xff\xfeignored\n")

    assert read_ignore_file_lines(gitignore_path) == ()


def test_read_ignore_file_lines_returns_empty_tuple_for_directory(tmp_path: Path) -> None:
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.mkdir()

    assert read_ignore_file_lines(gitignore_path) == ()
