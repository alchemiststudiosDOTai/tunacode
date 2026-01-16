#!/usr/bin/env python3
from __future__ import annotations

import ast
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

RG_BINARY = "rg"
CONSTANTS_PATH = Path("src/tunacode/constants.py")
SEARCH_ROOTS = (Path("src"), Path("tests"), Path("scripts"))
EXCLUDED_GLOBS = (
    "**/.git/**",
    "**/.venv/**",
    "**/.mypy_cache/**",
    "**/.pytest_cache/**",
    "**/.ruff_cache/**",
    "**/build/**",
    "**/dist/**",
    "**/node_modules/**",
)
WORD_BOUNDARY_FLAG = "-w"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_constant_name(name: str) -> bool:
    return name.isupper()


def iter_assigned_names(node: ast.AST) -> Iterable[str]:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                yield target.id
        return
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        yield node.target.id
        return


def load_module_constants(module: ast.Module) -> list[str]:
    constants: list[str] = []
    for statement in module.body:
        for name in iter_assigned_names(statement):
            if is_constant_name(name):
                constants.append(name)
    return constants


class ConstantUsageVisitor(ast.NodeVisitor):
    def __init__(self, constants: set[str]) -> None:
        self._constants = constants
        self.used: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in self._constants:
            self.used.add(node.id)
        self.generic_visit(node)


def load_used_in_constants_file(module: ast.Module, constants: set[str]) -> set[str]:
    visitor = ConstantUsageVisitor(constants)
    visitor.visit(module)
    return visitor.used


def build_rg_command(name: str) -> list[str]:
    base_command = [
        RG_BINARY,
        WORD_BOUNDARY_FLAG,
        name,
        "--glob",
        f"!{CONSTANTS_PATH.as_posix()}",
    ]
    for glob in EXCLUDED_GLOBS:
        base_command.extend(["--glob", f"!{glob}"])
    for root in SEARCH_ROOTS:
        if root.exists():
            base_command.append(root.as_posix())
    return base_command


def has_external_usage(name: str) -> bool:
    command = build_rg_command(name)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    error_message = result.stderr.strip()
    raise RuntimeError(f"rg failed for {name}: {error_message}")


def find_unused_constants(constants: list[str], used_in_file: set[str]) -> list[str]:
    unused: list[str] = []
    for name in constants:
        if name in used_in_file:
            continue
        if has_external_usage(name):
            continue
        unused.append(name)
    return unused


def is_rg_available() -> bool:
    """Check if ripgrep (rg) is available on PATH."""
    try:
        subprocess.run([RG_BINARY, "--version"], capture_output=True, check=False)
        return True
    except FileNotFoundError:
        return False


def main() -> int:
    if not is_rg_available():
        print(f"Skipping unused constants check: {RG_BINARY} not found on PATH")
        return 0

    if not CONSTANTS_PATH.exists():
        raise FileNotFoundError(f"Missing constants file: {CONSTANTS_PATH}")

    module_text = read_text(CONSTANTS_PATH)
    module = ast.parse(module_text, filename=str(CONSTANTS_PATH))
    constants = load_module_constants(module)
    constants_set = set(constants)
    used_in_file = load_used_in_constants_file(module, constants_set)
    unused_constants = find_unused_constants(constants, used_in_file)
    if not unused_constants:
        return 0

    unused_list = "\n".join(f"- {name}" for name in unused_constants)
    message = f"Unused constants detected in {CONSTANTS_PATH}:\n{unused_list}"
    print(message)
    return 1


if __name__ == "__main__":
    sys.exit(main())
