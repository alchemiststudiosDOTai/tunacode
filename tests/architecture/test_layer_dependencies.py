"""Architecture enforcement tests for dependency direction."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT_PARENT_INDEX = 2
SOURCE_DIR_NAME = "src"
PACKAGE_NAME = "tunacode"
MODULE_SEPARATOR = "."
PYTHON_FILE_GLOB = "*.py"
PRIVATE_MODULE_PREFIX = "_"
SOURCE_ENCODING = "utf-8"

LAYER_UI = "ui"
LAYER_CORE = "core"
LAYER_TOOLS = "tools"
LAYER_UTILS = "utils"
LAYER_TYPES = "types"

VIOLATION_ERROR_HEADER = "Forbidden imports found:"
EMPTY_PREFIXES: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceConfig:
    """Configuration for scanning source modules."""

    source_root: Path
    package_prefix: str
    module_separator: str
    python_file_glob: str
    private_module_prefix: str
    source_encoding: str


@dataclass(frozen=True)
class ModuleInfo:
    """Resolved module metadata for import scanning."""

    name: str
    path: Path


@dataclass(frozen=True)
class LayerRule:
    """Forbidden import prefixes for a given layer."""

    layer: str
    forbidden_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class KnownViolation:
    """Allowlisted import prefixes for a specific module."""

    module_name: str
    allowed_import_prefixes: tuple[str, ...]


TEST_FILE_PATH = Path(__file__).resolve()
REPO_ROOT = TEST_FILE_PATH.parents[REPO_ROOT_PARENT_INDEX]
SOURCE_ROOT = REPO_ROOT / SOURCE_DIR_NAME / PACKAGE_NAME
PACKAGE_PREFIX = f"{PACKAGE_NAME}{MODULE_SEPARATOR}"

UI_PREFIX = f"{PACKAGE_PREFIX}{LAYER_UI}"
CORE_PREFIX = f"{PACKAGE_PREFIX}{LAYER_CORE}"
TOOLS_PREFIX = f"{PACKAGE_PREFIX}{LAYER_TOOLS}"

SOURCE_CONFIG = SourceConfig(
    source_root=SOURCE_ROOT,
    package_prefix=PACKAGE_PREFIX,
    module_separator=MODULE_SEPARATOR,
    python_file_glob=PYTHON_FILE_GLOB,
    private_module_prefix=PRIVATE_MODULE_PREFIX,
    source_encoding=SOURCE_ENCODING,
)

LAYER_RULES: tuple[LayerRule, ...] = (
    LayerRule(layer=LAYER_CORE, forbidden_prefixes=(UI_PREFIX,)),
    LayerRule(layer=LAYER_TOOLS, forbidden_prefixes=(UI_PREFIX, CORE_PREFIX)),
    LayerRule(layer=LAYER_UTILS, forbidden_prefixes=(UI_PREFIX, CORE_PREFIX, TOOLS_PREFIX)),
    LayerRule(layer=LAYER_TYPES, forbidden_prefixes=(UI_PREFIX, CORE_PREFIX, TOOLS_PREFIX)),
)

KNOWN_VIOLATIONS: tuple[KnownViolation, ...] = ()


def _layer_rule_id(rule: LayerRule) -> str:
    """Provide a readable ID for parametrized layer rules."""

    return rule.layer


def _module_name_from_path(module_path: Path, config: SourceConfig) -> str:
    """Convert a file path to its module import path."""

    relative_path = module_path.relative_to(config.source_root)
    module_path_without_suffix = relative_path.with_suffix("")
    module_suffix = config.module_separator.join(module_path_without_suffix.parts)
    return f"{config.package_prefix}{module_suffix}"


def _discover_modules(layer: str, config: SourceConfig) -> list[ModuleInfo]:
    """Discover public modules within a layer directory."""

    package_dir = config.source_root / layer
    if not package_dir.exists():
        raise FileNotFoundError(f"Package directory not found: {package_dir}")

    python_files = sorted(package_dir.rglob(config.python_file_glob))
    modules: list[ModuleInfo] = []

    for python_file in python_files:
        file_name = python_file.name
        if file_name.startswith(config.private_module_prefix):
            continue

        module_name = _module_name_from_path(python_file, config)
        modules.append(ModuleInfo(name=module_name, path=python_file))

    return modules


def _get_imports(module_path: Path, config: SourceConfig) -> tuple[str, ...]:
    """Extract imports from a Python module."""

    source_text = module_path.read_text(encoding=config.source_encoding)
    parsed = ast.parse(source_text)
    imports: list[str] = []

    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        module_name = node.module
        if module_name is None:
            continue

        imports.append(module_name)

    return tuple(imports)


def _allowed_import_prefixes(
    module_name: str,
    known_violations: Sequence[KnownViolation],
    empty_prefixes: tuple[str, ...],
) -> tuple[str, ...]:
    """Return allowlisted import prefixes for a module, if any."""

    for violation in known_violations:
        if violation.module_name == module_name:
            return violation.allowed_import_prefixes

    return empty_prefixes


def _is_forbidden_import(
    imported_module: str,
    forbidden_prefixes: Sequence[str],
    allowed_prefixes: Sequence[str],
) -> bool:
    """Decide whether an import violates the layer constraints."""

    for allowed_prefix in allowed_prefixes:
        if imported_module.startswith(allowed_prefix):
            return False

    for forbidden_prefix in forbidden_prefixes:
        if imported_module.startswith(forbidden_prefix):
            return True

    return False


def _collect_violations(
    modules: Sequence[ModuleInfo],
    rule: LayerRule,
    known_violations: Sequence[KnownViolation],
    config: SourceConfig,
    empty_prefixes: tuple[str, ...],
) -> list[str]:
    """Collect forbidden import violations for a layer."""

    violations: list[str] = []
    forbidden_prefixes = rule.forbidden_prefixes

    for module in modules:
        module_imports = _get_imports(module.path, config)
        allowed_prefixes = _allowed_import_prefixes(
            module.name,
            known_violations,
            empty_prefixes,
        )

        for imported_module in module_imports:
            is_forbidden = _is_forbidden_import(
                imported_module,
                forbidden_prefixes,
                allowed_prefixes,
            )
            if not is_forbidden:
                continue

            violation = f"{module.name} imports {imported_module}"
            violations.append(violation)

    return violations


class TestLayerDependencies:
    """Verify dependency direction: ui -> core -> tools -> utils/types."""

    @pytest.mark.parametrize("rule", LAYER_RULES, ids=_layer_rule_id)
    def test_no_forbidden_imports(self, rule: LayerRule) -> None:
        """Each layer must not import from upper layers."""

        modules = _discover_modules(rule.layer, SOURCE_CONFIG)
        violations = _collect_violations(
            modules,
            rule,
            KNOWN_VIOLATIONS,
            SOURCE_CONFIG,
            EMPTY_PREFIXES,
        )

        assert not violations, f"{VIOLATION_ERROR_HEADER}\n" + "\n".join(violations)
