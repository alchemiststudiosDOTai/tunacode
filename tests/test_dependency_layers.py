"""Enforce layered architecture - no new violations allowed.

Run: uv run pytest tests/test_dependency_layers.py -v
"""

import grimp
import pytest

# Layer hierarchy (high to low)
LAYERS = ["ui", "core", "tools"]
UTILS_LEVEL = ["utils", "types", "configuration", "constants", "exceptions"]

# What each layer is allowed to import (besides utils-level)
# UI may only import core directly
ALLOWED_IMPORTS = {
    "ui": {"core"},
    "core": {"tools"},
    "tools": set(),
}


def get_layer(module: str) -> str | None:
    """Extract layer from module path."""
    parts = module.split(".")
    if len(parts) < 2:
        return None
    layer = parts[1]
    if layer in LAYERS or layer in UTILS_LEVEL:
        return layer
    return None


def is_valid_import(from_layer: str, to_layer: str) -> bool:
    """Check if import direction is valid."""
    if from_layer == "ui":
        return to_layer in {"ui", "core"}
    if to_layer in UTILS_LEVEL:
        return True
    if from_layer == to_layer:
        return True
    if from_layer in ALLOWED_IMPORTS:
        return to_layer in ALLOWED_IMPORTS[from_layer]
    return True


def find_violations() -> list[tuple[str, str, str, str]]:
    """Find all layer violations in the codebase."""
    g = grimp.build_graph("tunacode")
    violations = []

    for module in g.modules:
        from_layer = get_layer(module)
        if not from_layer:
            continue

        for imported in g.find_modules_directly_imported_by(module):
            to_layer = get_layer(imported)
            if to_layer and to_layer != from_layer and not is_valid_import(from_layer, to_layer):
                violations.append((from_layer, to_layer, module, imported))

    return violations


# Known violations we're actively fixing (baseline frozen 2026-01-26)
KNOWN_VIOLATIONS: set[tuple[str, str, str, str]] = set()


def test_known_violations_still_exist():
    """Track progress - remove from KNOWN_VIOLATIONS when fixed."""
    violations = set(find_violations())
    fixed = KNOWN_VIOLATIONS - violations

    if fixed:
        msg = "These violations have been FIXED - remove from KNOWN_VIOLATIONS:\n"
        for _from_l, _to_l, importer, imported in fixed:
            msg += f"  {importer} -> {imported}\n"
        pytest.fail(msg)
