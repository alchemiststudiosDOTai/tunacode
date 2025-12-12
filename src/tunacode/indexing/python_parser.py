"""Python source file parsing for code indexing.

This module handles extraction of symbols (classes, functions) and import
statements from Python source files.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_python_file(file_path: Path) -> tuple[set[str], list[str], list[str]]:
    """Extract imports, classes, and functions from a Python file.

    Uses fast line-by-line streaming parsing without AST to minimize overhead.

    Args:
        file_path: Path to the Python file to parse.

    Returns:
        Tuple of (imports, class_names, function_names).
        Returns empty sets/lists on file/IO errors.
    """
    imports: set[str] = set()
    classes: list[str] = []
    functions: list[str] = []

    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped = line.strip()
                _extract_import(stripped, imports)
                _extract_class(stripped, classes)
                _extract_function(stripped, functions)
    except OSError as e:
        logger.warning("Cannot read file %s: %s", file_path, e)
        return set(), [], []

    return imports, classes, functions


def _extract_import(line: str, imports: set[str]) -> None:
    """Extract module name from import statement."""
    if not line.startswith(("import ", "from ")):
        return

    parts = line.split()
    if len(parts) < 2:
        return

    if parts[0] == "import":
        remainder = line[len("import ") :]
        for item in remainder.split(","):
            name = item.strip().split()[0]
            if name:
                imports.add(name.split(".")[0])
        return

    if parts[0] == "from" and len(parts) >= 3:
        module = parts[1]
        base = module.split(".")[0]
        if base:
            imports.add(base)


def _extract_class(line: str, classes: list[str]) -> None:
    """Extract class name from class definition."""
    if not line.startswith("class ") or ":" not in line:
        return

    class_name = line[6:].split("(")[0].split(":")[0].strip()
    if class_name:
        classes.append(class_name)


def _extract_function(line: str, functions: list[str]) -> None:
    """Extract function name from function definition."""
    if not line.startswith("def ") or "(" not in line:
        return

    func_name = line[4:].split("(")[0].strip()
    if func_name:
        functions.append(func_name)
