"""Models and import/symbol extraction for stale symbol surface checks."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TARGET_ROOT = Path("src")
DEFAULT_SCAN_ROOTS = (Path("src"), Path("tests"))
PROJECT_PACKAGE = "tunacode"

VIOLATION_STALE_REEXPORTED_SYMBOL = "SSS001"
VIOLATION_STALE_ANNOTATION_SYMBOL = "SSS002"


@dataclass(frozen=True)
class ModuleInfo:
    path: Path
    module_name: str | None
    package_name: str | None
    is_package_init: bool
    tree: ast.Module


@dataclass(frozen=True)
class SymbolDef:
    module_name: str
    name: str
    path: Path
    line: int
    kind: str
    is_protocol: bool
    is_decorated: bool


@dataclass(frozen=True)
class Violation:
    code: str
    symbol: SymbolDef
    message: str

    def format(self) -> str:
        return f"{self.symbol.path}:{self.symbol.line}: {self.code} {self.message}"


SymbolKey = tuple[str, str]


def _is_protocol_base(base: ast.expr) -> bool:
    if isinstance(base, ast.Name):
        return base.id == "Protocol"
    if isinstance(base, ast.Attribute):
        return base.attr == "Protocol"
    if isinstance(base, ast.Subscript):
        return _is_protocol_base(base.value)
    return False


def _is_type_checking_expr(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Name):
        return expr.id == "TYPE_CHECKING"
    if isinstance(expr, ast.Attribute):
        return expr.attr == "TYPE_CHECKING"
    return False


def _module_info_for_path(root: Path, path: Path) -> tuple[str | None, str | None, bool]:
    rel_path = path.relative_to(root)
    parts = list(rel_path.parts)
    is_package_init = parts[-1] == "__init__.py"

    if root.name == "src":
        if parts[0] != PROJECT_PACKAGE:
            return None, None, is_package_init
        if is_package_init:
            module_name = ".".join(part for part in parts[:-1])
        else:
            module_name = ".".join(parts[:-1] + [parts[-1].removesuffix(".py")])
    else:
        if is_package_init:
            module_name = ".".join(part for part in parts[:-1]) or root.name
        else:
            module_name = ".".join([root.name] + parts[:-1] + [parts[-1].removesuffix(".py")])

    if not module_name:
        return None, None, is_package_init

    package_name = module_name if is_package_init else module_name.rsplit(".", 1)[0]
    return module_name, package_name, is_package_init


def _load_modules(roots: tuple[Path, ...]) -> list[ModuleInfo]:
    modules: list[ModuleInfo] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            module_name, package_name, is_package_init = _module_info_for_path(root, path)
            modules.append(
                ModuleInfo(
                    path=path,
                    module_name=module_name,
                    package_name=package_name,
                    is_package_init=is_package_init,
                    tree=tree,
                )
            )
    return modules


def _resolve_import_module(
    module: ModuleInfo, imported_module: str | None, level: int
) -> str | None:
    if level == 0:
        return imported_module
    if module.package_name is None:
        return None

    base_parts = module.package_name.split(".")
    up_levels = level - 1
    if up_levels > len(base_parts):
        return None
    resolved_parts = base_parts[: len(base_parts) - up_levels]
    if imported_module:
        resolved_parts.extend(imported_module.split("."))
    return ".".join(part for part in resolved_parts if part)


def _collect_symbol_defs(modules: list[ModuleInfo]) -> dict[SymbolKey, SymbolDef]:
    defs: dict[SymbolKey, SymbolDef] = {}
    for module in modules:
        if module.module_name is None or not module.module_name.startswith(PROJECT_PACKAGE):
            continue
        for node in module.tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            if node.name.startswith("_"):
                continue
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            defs[(module.module_name, node.name)] = SymbolDef(
                module_name=module.module_name,
                name=node.name,
                path=module.path,
                line=node.lineno,
                kind=kind,
                is_protocol=isinstance(node, ast.ClassDef)
                and any(_is_protocol_base(base) for base in node.bases),
                is_decorated=bool(node.decorator_list),
            )
    return defs


def _collect_re_exports(modules: list[ModuleInfo]) -> dict[SymbolKey, SymbolKey]:
    re_exports: dict[SymbolKey, SymbolKey] = {}
    for module in modules:
        if module.module_name is None or not module.is_package_init:
            continue
        for node in module.tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            resolved_module = _resolve_import_module(module, node.module, node.level)
            if resolved_module is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                exported_name = alias.asname or alias.name
                re_exports[(module.module_name, exported_name)] = (resolved_module, alias.name)
    return re_exports


def _resolve_symbol(
    module_name: str, symbol_name: str, re_exports: dict[SymbolKey, SymbolKey]
) -> SymbolKey:
    current = (module_name, symbol_name)
    seen: set[SymbolKey] = set()
    while current in re_exports and current not in seen:
        seen.add(current)
        current = re_exports[current]
    return current
