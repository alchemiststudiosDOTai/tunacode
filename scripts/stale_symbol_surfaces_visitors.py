"""AST visitors for internal and external symbol reference tracking."""

from __future__ import annotations

import ast
from collections import defaultdict

from stale_symbol_surfaces_models import (
    ModuleInfo,
    SymbolDef,
    SymbolKey,
    _is_type_checking_expr,
    _resolve_import_module,
    _resolve_symbol,
)


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
