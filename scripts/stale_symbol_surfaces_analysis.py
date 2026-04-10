"""Liveness analysis and stale symbol surface violation reporting."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

from stale_symbol_surfaces_models import (
    DEFAULT_SCAN_ROOTS,
    DEFAULT_TARGET_ROOT,
    VIOLATION_STALE_ANNOTATION_SYMBOL,
    VIOLATION_STALE_REEXPORTED_SYMBOL,
    ModuleInfo,
    SymbolDef,
    SymbolKey,
    Violation,
    _collect_re_exports,
    _collect_symbol_defs,
    _load_modules,
)
from stale_symbol_surfaces_visitors import ExternalReferenceVisitor, InternalReferenceVisitor


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
