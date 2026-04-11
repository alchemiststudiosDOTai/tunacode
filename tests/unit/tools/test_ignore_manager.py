from __future__ import annotations

from pathlib import Path

from tunacode.tools.ignore_manager import read_gitignore_lines


def test_read_gitignore_lines_returns_empty_tuple_for_invalid_utf8(
    tmp_path: Path,
) -> None:
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_bytes(b"\xff\xfeignored-dir/\n")

    assert read_gitignore_lines(gitignore_path) == ()
