#!/usr/bin/env python3
"""Check for unused Python modules (never imported anywhere).

This checks if a module file is used via:
- Direct imports in the codebase
- __init__.py exports
- console_scripts entry points in pyproject.toml
"""

import ast
import sys
from collections.abc import Set
from pathlib import Path


def get_import_names(import_node: ast.Import | ast.ImportFrom) -> Set[str]:
    """Extract module names from an import node."""
    names: Set[str] = set()

    if isinstance(import_node, ast.Import):
        for alias in import_node.names:
            full_name = alias.name
            names.add(full_name)
            # For direct imports like "import foo.bar", also count "foo" as used
            # because importing the parent uses the submodule
            if "." in full_name:
                names.add(full_name.split(".")[0])

    elif isinstance(import_node, ast.ImportFrom) and import_node.module:
        # For "from X import Y", only add X (not all parents)
        # This is because importing from a submodule doesn't mean the parent is "used"
        names.add(import_node.module)

    return names


def get_all_imports(src_dir: Path) -> Set[str]:
    """Find all module imports in the codebase."""
    imports: Set[str] = set()

    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text()
            tree = ast.parse(content, filename=str(py_file))

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.update(get_import_names(node))

        except (SyntaxError, ValueError):
            continue

    return imports


def get_init_exports(src_dir: Path) -> Set[str]:
    """Get all module names exported via __init__.py."""
    exports: Set[str] = set()

    for init_file in src_dir.rglob("__init__.py"):
        try:
            content = init_file.read_text()
            tree = ast.parse(content, filename=str(init_file))

            # Get parent module name
            rel_path = init_file.relative_to(src_dir)
            parts = list(rel_path.parts[:-1])  # Exclude __init__.py

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    # "from .sub import X" or "from . import X"
                    for alias in node.names:
                        if node.level > 0:  # Relative import
                            parent = ".".join(parts) if parts else ""
                            if parent:
                                exports.add(f"{parent}.{alias.name}")
                            else:
                                exports.add(alias.name)
                        else:
                            exports.add(node.module)

        except (SyntaxError, ValueError):
            continue

    return exports


def get_entry_points(pyproject: Path) -> Set[str]:
    """Get console_scripts entry points from pyproject.toml."""
    imports: Set[str] = set()

    if not pyproject.exists():
        return imports

    content = pyproject.read_text()

    in_scripts = False

    for line in content.split("\n"):
        line = line.strip()

        if line == "[project.scripts]":
            in_scripts = True
            continue
        elif line.startswith("[") and in_scripts:
            in_scripts = False

        if in_scripts and "=" in line and '"' in line:
            # Line format: tunacode = "tunacode.ui.main:app"
            right_side = line.split("=")[1].strip().strip('"')
            # "tunacode.ui.main:app" -> "tunacode.ui.main"
            module = right_side.split(":")[0]
            imports.add(module)

    return imports


def get_module_names(src_dir: Path) -> dict[str, Path]:
    """Get all module names and their file paths."""
    modules: dict[str, Path] = {}

    for py_file in src_dir.rglob("*.py"):
        rel_path = py_file.relative_to(src_dir)

        parts = list(rel_path.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1].removesuffix(".py")

        if parts:
            module_name = ".".join(parts)
            modules[module_name] = py_file

    return modules


def check_unused_modules(src_dir: Path) -> list[tuple[str, Path]]:
    """Find Python files that are never imported."""
    imports = get_all_imports(src_dir)
    exports = get_init_exports(src_dir)
    entry_points = get_entry_points(src_dir / ".." / "pyproject.toml")

    # Add parent packages of entry points
    # e.g., "tunacode.ui.main" -> add "tunacode.ui" and "tunacode"
    for ep in entry_points:
        parts = ep.split(".")
        for i in range(1, len(parts)):
            imports.add(".".join(parts[:i]))

    # Combine all "used" modules
    used = imports | exports | entry_points

    modules = get_module_names(src_dir)

    unused: list[tuple[str, Path]] = []

    for module_name, py_file in modules.items():
        # Skip private modules
        if any(part.startswith("_") for part in module_name.split(".")):
            continue

        # Check if this module is used
        parts = module_name.split(".")
        is_used = False
        for i in range(1, len(parts) + 1):
            parent = ".".join(parts[:i])
            if parent in used:
                is_used = True
                break

        if not is_used:
            unused.append((module_name, py_file))

    return unused


def main() -> int:
    src_dir = Path("src")

    if not src_dir.exists():
        print("src directory not found")
        return 1

    unused = check_unused_modules(src_dir)

    if unused:
        print("WARNING: The following Python files are never used:")
        for module_name, _ in sorted(unused):
            print(f"  - {module_name}")
        print(f"\nTotal: {len(unused)} unused modules")
        return 1

    print("All Python files are used somewhere.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
