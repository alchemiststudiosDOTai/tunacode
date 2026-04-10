#!/usr/bin/env python3
"""Detect stale public symbols masked by local type scaffolding."""

from __future__ import annotations

import ast
import sys
from collections import defaultdict, deque
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


class InternalReferenceVisitor(ast.NodeVisitor):
    def __init__(self, module_name: str, top_level_defs: set[str]) -> None:
        self.module_name = module_name
        self.top_level_defs = top_level_defs
        self.runtime_edges: dict[str | None, set[str]] = defaultdict(set)
        self.annotation_edges: dict[str, set[str]] = defaultdict(set)
        self.annotation_refs: dict[str, int] = defaultdict(int)
        self._owner_stack: list[str | None] = [None]
        self._annotation_depth = 0
        self._type_checking_depth = 0

    @property
    def _owner(self) -> str | None:
        return self._owner_stack[-1]

    def _add_ref(self, name: str) -> None:
        if name not in self.top_level_defs:
            return
        owner = self._owner
        if self._annotation_depth > 0:
            if owner is not None:
                self.annotation_edges[owner].add(name)
                self.annotation_refs[name] += 1
            return
        self.runtime_edges[owner].add(name)

    def _visit_annotation(self, node: ast.AST | None) -> None:
        if node is None:
            return
        self._annotation_depth += 1
        self.visit(node)
        self._annotation_depth -= 1

    def _visit_statements(self, statements: list[ast.stmt]) -> None:
        for statement in statements:
            self.visit(statement)

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_expr(node.test):
            self._type_checking_depth += 1
            self._visit_statements(node.body)
            self._type_checking_depth -= 1
            self._visit_statements(node.orelse)
            return
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if self._type_checking_depth > 0 and self._annotation_depth == 0:
            return
        self._add_ref(node.id)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.target)
        self._visit_annotation(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def visit_arg(self, node: ast.arg) -> None:
        self._visit_annotation(node.annotation)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        is_top_level = self._owner is None and node.name in self.top_level_defs
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in node.args.defaults:
            self.visit(default)
        for default in node.args.kw_defaults:
            if default is not None:
                self.visit(default)
        next_owner = node.name if is_top_level else self._owner
        self._owner_stack.append(next_owner)
        self._visit_annotation(node.returns)
        self.visit(node.args)
        self._visit_statements(node.body)
        self._owner_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        is_top_level = self._owner is None and node.name in self.top_level_defs
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)
        next_owner = node.name if is_top_level else self._owner
        self._owner_stack.append(next_owner)
        self._visit_statements(node.body)
        self._owner_stack.pop()


class ExternalReferenceVisitor(ast.NodeVisitor):
    def __init__(
        self,
        module: ModuleInfo,
        symbol_defs: dict[SymbolKey, SymbolDef],
        re_exports: dict[SymbolKey, SymbolKey],
    ) -> None:
        self.module = module
        self.symbol_defs = symbol_defs
        self.re_exports = re_exports
        self.strong_refs: dict[SymbolKey, int] = defaultdict(int)
        self.weak_re_exports: dict[SymbolKey, int] = defaultdict(int)
        self._imported_symbols: dict[str, SymbolKey] = {}
        self._module_aliases: dict[str, str] = {}
        self._annotation_depth = 0
        self._type_checking_depth = 0

    def _record_symbol_import(self, alias_name: str, module_name: str, symbol_name: str) -> None:
        origin = _resolve_symbol(module_name, symbol_name, self.re_exports)
        self._imported_symbols[alias_name] = origin
        if origin not in self.symbol_defs:
            return
        if self.module.module_name == origin[0]:
            return
        if self.module.is_package_init and self._type_checking_depth == 0:
            self.weak_re_exports[origin] += 1
            return
        self.strong_refs[origin] += 1

    def _record_module_alias(self, alias_name: str, module_name: str) -> None:
        self._module_aliases[alias_name] = module_name

    def _visit_annotation(self, node: ast.AST | None) -> None:
        if node is None:
            return
        self._annotation_depth += 1
        self.visit(node)
        self._annotation_depth -= 1

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_expr(node.test):
            self._type_checking_depth += 1
            for statement in node.body:
                self.visit(statement)
            self._type_checking_depth -= 1
            for statement in node.orelse:
                self.visit(statement)
            return
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        resolved_module = _resolve_import_module(self.module, node.module, node.level)
        if resolved_module is None:
            return
        for alias in node.names:
            if alias.name == "*":
                continue
            self._record_symbol_import(alias.asname or alias.name, resolved_module, alias.name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".")[0]
            self._record_module_alias(local_name, alias.name)

    def visit_Name(self, node: ast.Name) -> None:
        origin = self._imported_symbols.get(node.id)
        if origin is None or origin not in self.symbol_defs:
            return
        if self.module.module_name == origin[0]:
            return
        if self.module.is_package_init:
            self.strong_refs[origin] += 1
            return
        if self._type_checking_depth == 0 or self._annotation_depth > 0:
            self.strong_refs[origin] += 1

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.visit(node.value)
        if not isinstance(node.value, ast.Name):
            return
        imported_module = self._module_aliases.get(node.value.id)
        if imported_module is None:
            return
        origin = _resolve_symbol(imported_module, node.attr, self.re_exports)
        if origin not in self.symbol_defs:
            return
        if self.module.module_name == origin[0]:
            return
        self.strong_refs[origin] += 1

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.target)
        self._visit_annotation(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def visit_arg(self, node: ast.arg) -> None:
        self._visit_annotation(node.annotation)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in node.args.defaults:
            self.visit(default)
        for default in node.args.kw_defaults:
            if default is not None:
                self.visit(default)
        self._visit_annotation(node.returns)
        self.visit(node.args)
        for statement in node.body:
            self.visit(statement)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)


def _collect_internal_analysis(
    modules: list[ModuleInfo], symbol_defs: dict[SymbolKey, SymbolDef]
) -> tuple[
    dict[SymbolKey, set[SymbolKey]],
    dict[SymbolKey, set[SymbolKey]],
    dict[SymbolKey, bool],
    dict[SymbolKey, int],
]:
    runtime_edges: dict[SymbolKey, set[SymbolKey]] = defaultdict(set)
    annotation_edges: dict[SymbolKey, set[SymbolKey]] = defaultdict(set)
    module_roots: dict[SymbolKey, bool] = defaultdict(bool)
    annotation_refs: dict[SymbolKey, int] = defaultdict(int)

    defs_by_module: dict[str, set[str]] = defaultdict(set)
    for module_name, symbol_name in symbol_defs:
        defs_by_module[module_name].add(symbol_name)

    for module in modules:
        if module.module_name is None or module.module_name not in defs_by_module:
            continue
        visitor = InternalReferenceVisitor(module.module_name, defs_by_module[module.module_name])
        visitor.visit(module.tree)

        for target_name in visitor.runtime_edges.get(None, set()):
            module_roots[(module.module_name, target_name)] = True
        for owner_name, targets in visitor.runtime_edges.items():
            if owner_name is None:
                continue
            owner = (module.module_name, owner_name)
            runtime_edges[owner].update(
                (module.module_name, target_name) for target_name in targets
            )
        for owner_name, targets in visitor.annotation_edges.items():
            owner = (module.module_name, owner_name)
            annotation_edges[owner].update(
                (module.module_name, target_name) for target_name in targets
            )
        for target_name, count in visitor.annotation_refs.items():
            annotation_refs[(module.module_name, target_name)] += count

    return runtime_edges, annotation_edges, module_roots, annotation_refs


def _collect_external_refs(
    modules: list[ModuleInfo],
    symbol_defs: dict[SymbolKey, SymbolDef],
    re_exports: dict[SymbolKey, SymbolKey],
) -> tuple[dict[SymbolKey, int], dict[SymbolKey, int]]:
    strong_refs: dict[SymbolKey, int] = defaultdict(int)
    weak_re_exports: dict[SymbolKey, int] = defaultdict(int)

    for module in modules:
        visitor = ExternalReferenceVisitor(module, symbol_defs, re_exports)
        visitor.visit(module.tree)
        for symbol, count in visitor.strong_refs.items():
            strong_refs[symbol] += count
        for symbol, count in visitor.weak_re_exports.items():
            weak_re_exports[symbol] += count

    return strong_refs, weak_re_exports


def _seed_live_symbols(
    symbol_defs: dict[SymbolKey, SymbolDef],
    target_root: Path,
    strong_refs: dict[SymbolKey, int],
    module_roots: dict[SymbolKey, bool],
) -> tuple[set[SymbolKey], deque[SymbolKey]]:
    live_symbols: set[SymbolKey] = set()
    queue: deque[SymbolKey] = deque()

    for symbol, symbol_def in symbol_defs.items():
        if not symbol_def.path.is_relative_to(target_root):
            continue
        is_live_root = (
            strong_refs.get(symbol, 0) > 0
            or module_roots.get(symbol, False)
            or symbol_def.is_decorated
        )
        if not is_live_root:
            continue
        live_symbols.add(symbol)
        queue.append(symbol)

    return live_symbols, queue


def _propagate_liveness(
    live_symbols: set[SymbolKey],
    queue: deque[SymbolKey],
    runtime_edges: dict[SymbolKey, set[SymbolKey]],
    annotation_edges: dict[SymbolKey, set[SymbolKey]],
) -> None:
    while queue:
        current = queue.popleft()
        for target in runtime_edges.get(current, set()) | annotation_edges.get(current, set()):
            if target in live_symbols:
                continue
            live_symbols.add(target)
            queue.append(target)


def _collect_reverse_annotation_edges(
    annotation_edges: dict[SymbolKey, set[SymbolKey]],
) -> dict[SymbolKey, set[SymbolKey]]:
    reverse_annotation_edges: dict[SymbolKey, set[SymbolKey]] = defaultdict(set)
    for owner, targets in annotation_edges.items():
        for target in targets:
            reverse_annotation_edges[target].add(owner)
    return reverse_annotation_edges


def _sorted_symbol_items(
    symbol_defs: dict[SymbolKey, SymbolDef],
) -> list[tuple[SymbolKey, SymbolDef]]:
    return sorted(symbol_defs.items(), key=lambda item: (str(item[1].path), item[1].line))


def _build_stale_annotation_cluster_violations(
    symbol_defs: dict[SymbolKey, SymbolDef],
    target_root: Path,
    live_symbols: set[SymbolKey],
    annotation_refs: dict[SymbolKey, int],
    reverse_annotation_edges: dict[SymbolKey, set[SymbolKey]],
    weak_re_exports: dict[SymbolKey, int],
) -> list[Violation]:
    violations: list[Violation] = []
    seen: set[tuple[str, SymbolKey]] = set()

    for symbol, symbol_def in _sorted_symbol_items(symbol_defs):
        if not symbol_def.path.is_relative_to(target_root) or symbol in live_symbols:
            continue

        weak_annotation_count = annotation_refs.get(symbol, 0)
        if weak_annotation_count == 0:
            continue

        stale_exported_owners = sorted(
            owner
            for owner in reverse_annotation_edges.get(symbol, set())
            if owner not in live_symbols and weak_re_exports.get(owner, 0) > 0
        )
        if not stale_exported_owners:
            continue

        annotation_key = (VIOLATION_STALE_ANNOTATION_SYMBOL, symbol)
        if annotation_key not in seen:
            violations.append(
                Violation(
                    code=VIOLATION_STALE_ANNOTATION_SYMBOL,
                    symbol=symbol_def,
                    message=(
                        f"public {symbol_def.kind} '{symbol_def.name}' is only referenced by "
                        f"{weak_annotation_count} same-module annotation(s) on "
                        "stale re-exported surface(s)"
                    ),
                )
            )
            seen.add(annotation_key)

        for owner in stale_exported_owners:
            owner_key = (VIOLATION_STALE_REEXPORTED_SYMBOL, owner)
            if owner_key in seen:
                continue
            owner_def = symbol_defs[owner]
            violations.append(
                Violation(
                    code=VIOLATION_STALE_REEXPORTED_SYMBOL,
                    symbol=owner_def,
                    message=(
                        f"public {owner_def.kind} '{owner_def.name}' is only kept alive by "
                        f"{weak_re_exports[owner]} package re-export(s) and depends on "
                        "stale local type scaffolding"
                    ),
                )
            )
            seen.add(owner_key)

    return sorted(
        violations,
        key=lambda violation: (
            str(violation.symbol.path),
            violation.symbol.line,
            violation.code,
        ),
    )


def find_stale_symbol_surface_violations(
    target_root: Path = DEFAULT_TARGET_ROOT, scan_roots: tuple[Path, ...] = DEFAULT_SCAN_ROOTS
) -> list[Violation]:
    modules = _load_modules(scan_roots)
    symbol_defs = _collect_symbol_defs(modules)
    re_exports = _collect_re_exports(modules)
    runtime_edges, annotation_edges, module_roots, annotation_refs = _collect_internal_analysis(
        modules, symbol_defs
    )
    strong_refs, weak_re_exports = _collect_external_refs(modules, symbol_defs, re_exports)

    live_symbols, queue = _seed_live_symbols(
        symbol_defs=symbol_defs,
        target_root=target_root,
        strong_refs=strong_refs,
        module_roots=module_roots,
    )
    _propagate_liveness(
        live_symbols=live_symbols,
        queue=queue,
        runtime_edges=runtime_edges,
        annotation_edges=annotation_edges,
    )
    reverse_annotation_edges = _collect_reverse_annotation_edges(annotation_edges)

    return _build_stale_annotation_cluster_violations(
        symbol_defs=symbol_defs,
        target_root=target_root,
        live_symbols=live_symbols,
        annotation_refs=annotation_refs,
        reverse_annotation_edges=reverse_annotation_edges,
        weak_re_exports=weak_re_exports,
    )


def main(argv: list[str]) -> int:
    target_root = Path(argv[0]) if argv else DEFAULT_TARGET_ROOT
    scan_roots = tuple(Path(arg) for arg in argv[1:]) if len(argv) > 1 else DEFAULT_SCAN_ROOTS

    violations = find_stale_symbol_surface_violations(
        target_root=target_root,
        scan_roots=scan_roots,
    )
    if violations:
        print("Stale symbol surface violations found:\n")
        for violation in violations:
            print(f"  {violation.format()}")
        print(f"\nTotal: {len(violations)}")
        return 1

    print("No stale symbol surface violations found")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
