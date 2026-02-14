"""Prevent __init__.py bloat - no class definitions, keep them thin.

Run: uv run pytest tests/test_init_bloat.py -v
"""

from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).parent.parent / "src" / "tunacode"

MAX_INIT_LINES = 80


def _collect_init_files() -> list[Path]:
    return sorted(SRC_ROOT.rglob("__init__.py"))


def _find_class_definitions(path: Path) -> list[str]:
    violations = []
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        if line.startswith("class "):
            violations.append(f"{path.relative_to(SRC_ROOT)}:{i} -> {line.strip()}")
    return violations


@pytest.mark.parametrize(
    "init_file", _collect_init_files(), ids=lambda p: str(p.relative_to(SRC_ROOT))
)
def test_no_class_definitions_in_init(init_file: Path) -> None:
    """__init__.py should be thin glue — no class definitions."""
    violations = _find_class_definitions(init_file)
    assert not violations, (
        "Class definitions found in __init__.py (move to own module):\n"
        + "\n".join(f"  {v}" for v in violations)
    )


@pytest.mark.parametrize(
    "init_file", _collect_init_files(), ids=lambda p: str(p.relative_to(SRC_ROOT))
)
def test_init_file_not_bloated(init_file: Path) -> None:
    """__init__.py should stay under {MAX_INIT_LINES} lines."""
    line_count = len(init_file.read_text().splitlines())
    assert line_count <= MAX_INIT_LINES, (
        f"{init_file.relative_to(SRC_ROOT)} has {line_count} lines "
        f"(max {MAX_INIT_LINES}). Split business logic into own modules."
    )
