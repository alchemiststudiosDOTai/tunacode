"""Check that everything that is included as objects defining the public API of a module or package is defined."""

import ast
from pathlib import Path

from .test_import_order import SOURCE_ROOT as source_root


def get_imports(init_file: Path) -> list[str]:
    """Get all objects except __all__."""

    with open(init_file, "r") as f:
        root = ast.parse(f.read())

    objects = []

    for node in ast.iter_child_nodes(root):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.asname:
                    objects.append(alias.asname)
                else:
                    objects.append(alias.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id != "__all__":
                    objects.append(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id != "__all__":
                objects.append(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            objects.append(node.name)
    
    return objects


def get_public_imports(init_file: Path) -> list[str]:
    """Get all public imports."""

    with open(init_file, "r") as f:
        root = ast.parse(f.read())

    for node in ast.iter_child_nodes(root):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    return [elt.value for elt in node.value.elts]
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                return [elt.value for elt in node.value.elts]

    return []


def test_all_exported_imports() -> None:
    """Verify that all imports in __init__ files are equal to the public imports in __all__."""

    for init_file in source_root.rglob("__init__.py"):
        public_imports = get_public_imports(init_file)
        if not public_imports:
            continue
        imports = get_imports(init_file)
        assert(set(public_imports).issubset(set(imports)))
