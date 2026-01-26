"""Import order enforcement for first-party modules."""

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

LAYER_RANK_START = 0
MIN_IMPORT_COUNT = 2
FIRST_INDEX = 0

PACKAGE_PREFIX = f"{PACKAGE_NAME}{MODULE_SEPARATOR}"

IMPORT_ORDER_ERROR_HEADER = "First-party imports out of layer order:"
UNKNOWN_LAYER_ERROR = "Unknown tunacode import root: {root}"
IMPORT_LINE_FORMAT = "{module} (line {line})"
SECTION_ACTUAL = "Actual:"
SECTION_EXPECTED = "Expected:"
NEWLINE = "\n"

SHARED_LAYER_MODULES: tuple[str, ...] = (
    "configuration",
    "constants",
    "exceptions",
    "indexing",
    "lsp",
    "prompts",
    "templates",
    "types",
    "utils",
)
LAYERED_MODULES: tuple[str, ...] = ("tools", "core", "ui")
ORDERED_LAYER_MODULES: tuple[str, ...] = SHARED_LAYER_MODULES + LAYERED_MODULES


@dataclass(frozen=True)
class SourceConfig:
    """Configuration for scanning source modules."""

    source_root: Path
    python_file_glob: str
    private_module_prefix: str
    source_encoding: str


@dataclass(frozen=True)
class ImportOrderConfig:
    """Configuration for first-party import ordering."""

    package_prefix: str
    module_separator: str
    layer_ranks: dict[str, int]
    unknown_layer_error: str


@dataclass(frozen=True)
class ModuleInfo:
    """Resolved module metadata for import scanning."""

    path: Path
    relative_path: Path


@dataclass(frozen=True)
class ImportOccurrence:
    """Track a first-party import with line number."""

    module_name: str
    line_number: int


ImportKey = tuple[int, str]

TEST_FILE_PATH = Path(__file__).resolve()
REPO_ROOT = TEST_FILE_PATH.parents[REPO_ROOT_PARENT_INDEX]
SOURCE_ROOT = REPO_ROOT / SOURCE_DIR_NAME / PACKAGE_NAME

LAYER_RANKS = {
    layer: index for index, layer in enumerate(ORDERED_LAYER_MODULES, start=LAYER_RANK_START)
}

SOURCE_CONFIG = SourceConfig(
    source_root=SOURCE_ROOT,
    python_file_glob=PYTHON_FILE_GLOB,
    private_module_prefix=PRIVATE_MODULE_PREFIX,
    source_encoding=SOURCE_ENCODING,
)

IMPORT_ORDER_CONFIG = ImportOrderConfig(
    package_prefix=PACKAGE_PREFIX,
    module_separator=MODULE_SEPARATOR,
    layer_ranks=LAYER_RANKS,
    unknown_layer_error=UNKNOWN_LAYER_ERROR,
)


def _module_id(module_info: ModuleInfo) -> str:
    """Provide a readable ID for parametrized modules."""

    return str(module_info.relative_path)


def _discover_modules(config: SourceConfig, repo_root: Path) -> list[ModuleInfo]:
    """Discover public modules within the source directory."""

    python_files = sorted(config.source_root.rglob(config.python_file_glob))
    modules: list[ModuleInfo] = []

    for python_file in python_files:
        file_name = python_file.name
        if file_name.startswith(config.private_module_prefix):
            continue

        relative_path = python_file.relative_to(repo_root)
        modules.append(ModuleInfo(path=python_file, relative_path=relative_path))

    return modules


def _first_party_imports(
    module_path: Path,
    config: ImportOrderConfig,
    source_encoding: str,
) -> list[ImportOccurrence]:
    """Extract first-party imports from a Python module."""

    source_text = module_path.read_text(encoding=source_encoding)
    parsed = ast.parse(source_text)
    imports: list[ImportOccurrence] = []

    for node in parsed.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                if not module_name.startswith(config.package_prefix):
                    continue
                imports.append(ImportOccurrence(module_name=module_name, line_number=node.lineno))
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        module_name = node.module
        if module_name is None:
            continue

        if not module_name.startswith(config.package_prefix):
            continue

        imports.append(ImportOccurrence(module_name=module_name, line_number=node.lineno))

    return imports


def _top_level_module(module_name: str, config: ImportOrderConfig) -> str:
    """Extract the top-level package name from a module import."""

    prefix = config.package_prefix
    module_suffix = module_name.removeprefix(prefix)
    if not module_suffix:
        return ""

    module_parts = module_suffix.split(config.module_separator)
    return module_parts[FIRST_INDEX]


def _layer_rank(module_name: str, config: ImportOrderConfig) -> int:
    """Resolve the layer rank for an import module."""

    top_level = _top_level_module(module_name, config)
    rank = config.layer_ranks.get(top_level)
    if rank is None:
        error_message = config.unknown_layer_error.format(root=top_level)
        raise AssertionError(error_message)

    return rank


def _import_key(entry: ImportOccurrence, config: ImportOrderConfig) -> ImportKey:
    """Return the sortable import key for an entry."""

    module_name = entry.module_name
    rank = _layer_rank(module_name, config)
    return (rank, module_name)


def _format_imports(imports: Sequence[ImportOccurrence]) -> str:
    """Format imports with line numbers for debug output."""

    lines = [
        IMPORT_LINE_FORMAT.format(module=entry.module_name, line=entry.line_number)
        for entry in imports
    ]
    return NEWLINE.join(lines)


def _sorted_imports(
    imports: Sequence[ImportOccurrence],
    config: ImportOrderConfig,
) -> list[ImportOccurrence]:
    """Return imports sorted by layer rank and module name."""

    return sorted(imports, key=lambda entry: _import_key(entry, config))


@pytest.mark.parametrize(
    "module_info",
    _discover_modules(SOURCE_CONFIG, REPO_ROOT),
    ids=_module_id,
)
def test_first_party_import_order(module_info: ModuleInfo) -> None:
    """Ensure first-party imports follow the layer flow order."""

    imports = _first_party_imports(
        module_info.path,
        IMPORT_ORDER_CONFIG,
        SOURCE_CONFIG.source_encoding,
    )
    import_count = len(imports)
    if import_count < MIN_IMPORT_COUNT:
        return

    actual_keys = [_import_key(entry, IMPORT_ORDER_CONFIG) for entry in imports]
    expected_keys = sorted(actual_keys)
    if actual_keys == expected_keys:
        return

    expected_imports = _sorted_imports(imports, IMPORT_ORDER_CONFIG)
    actual_display = _format_imports(imports)
    expected_display = _format_imports(expected_imports)
    error_details = NEWLINE.join(
        [
            IMPORT_ORDER_ERROR_HEADER,
            str(module_info.relative_path),
            SECTION_ACTUAL,
            actual_display,
            SECTION_EXPECTED,
            expected_display,
        ]
    )
    raise AssertionError(error_details)
