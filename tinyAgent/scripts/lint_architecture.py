#!/usr/bin/env python3
"""Architecture linter: catches logic/boundary violations that ruff and mypy cannot.

Rules
-----
ARCH001  Library code must not load .env files.
         Environment configuration is the caller's job, not the library's.
         Providers and core modules must never call load_dotenv() or import dotenv.

ARCH002  Provider modules must not mutate os.environ.
         Providers consume configuration; they do not set it.

ARCH003  __init__.py must only re-export from core modules.
         Optional providers (those requiring external/non-PyPI deps) are imported
         directly by the caller, not wired into the package namespace.

ARCH004  No NIH (not-invented-here) utility modules.
         Do not ship hand-rolled reimplementations of well-known packages.
         Use the real dependency or do without it.

Configuration lives in pyproject.toml under [tool.archlint]:

    [tool.archlint]
    library_root = "tinyagent"
    core_modules = [
        "agent", "agent_loop", "agent_tool_execution", "agent_types",
        "openrouter_provider", "proxy", "proxy_event_handlers",
    ]
    nih_filenames = ["dotenv.py", "six.py", "compat.py"]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "library_root": "tinyagent",
    "core_modules": [
        "agent",
        "agent_loop",
        "agent_tool_execution",
        "agent_types",
        "openrouter_provider",
        "proxy",
        "proxy_event_handlers",
    ],
    "nih_filenames": ["dotenv.py", "six.py", "compat.py"],
}


def _load_config() -> dict:
    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        data = tomllib.loads(pyproject.read_text())
        return {**_DEFAULTS, **data.get("tool", {}).get("archlint", {})}
    return dict(_DEFAULTS)


# ---------------------------------------------------------------------------
# Violation type
# ---------------------------------------------------------------------------

Violation = tuple[str, int, str, str]  # (file, line, rule_id, message)


# ---------------------------------------------------------------------------
# Per-rule checkers
# ---------------------------------------------------------------------------


def _check_arch001(rel: str, lineno: int, stripped: str) -> list[Violation]:
    """ARCH001: no dotenv in library code."""
    errs: list[Violation] = []
    if re.search(r"\bload_dotenv\b", stripped):
        errs.append((rel, lineno, "ARCH001", "Library code must not call load_dotenv()"))
    if re.search(r"(from\s+\.?dotenv\s+import|import\s+dotenv)", stripped):
        errs.append((rel, lineno, "ARCH001", "Library code must not import dotenv"))
    return errs


def _check_arch002(rel: str, lineno: int, stripped: str) -> list[Violation]:
    """ARCH002: providers must not mutate os.environ."""
    errs: list[Violation] = []
    if re.search(r"os\.environ\s*\[.*\]\s*=", stripped):
        errs.append((rel, lineno, "ARCH002", "Provider must not write to os.environ"))
    if re.search(r"os\.environ\.(setdefault|update)\s*\(", stripped):
        errs.append((rel, lineno, "ARCH002", "Provider must not mutate os.environ"))
    return errs


def _check_arch003(
    rel: str,
    lineno: int,
    stripped: str,
    core_modules: list[str],
) -> list[Violation]:
    """ARCH003: __init__.py imports only core modules."""
    m = re.match(r"from\s+\.(\w+)\s+import", stripped)
    if not m:
        return []
    module_name = m.group(1)
    if module_name in core_modules:
        return []
    return [
        (
            rel,
            lineno,
            "ARCH003",
            f"__init__.py imports from non-core module '.{module_name}'. "
            f"Optional providers must be imported directly by the caller, "
            f"not re-exported from the package root.",
        )
    ]


# ---------------------------------------------------------------------------
# File-level checks
# ---------------------------------------------------------------------------


def _violations_in_file(
    path: Path,
    lines: list[str],
    cfg: dict,
) -> list[Violation]:
    errs: list[Violation] = []
    rel = str(path)
    lib_root = cfg["library_root"]
    is_library = rel.startswith(lib_root + "/") or rel.startswith(lib_root + "\\")

    if not is_library:
        return errs

    is_init = path.name == "__init__.py"
    is_provider = path.name.endswith("_provider.py")

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        errs.extend(_check_arch001(rel, lineno, stripped))

        if is_provider:
            errs.extend(_check_arch002(rel, lineno, stripped))

        if is_init:
            errs.extend(_check_arch003(rel, lineno, stripped, cfg["core_modules"]))

    # ARCH004: NIH filenames
    if path.name in cfg["nih_filenames"]:
        errs.append(
            (
                rel,
                0,
                "ARCH004",
                f"NIH module '{path.name}' duplicates a well-known package. "
                f"Use the real dependency or remove it.",
            )
        )

    return errs


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_SKIP_DIRS = {".ruff_cache", "__pycache__", ".venv", ".mypy_cache", "target", ".git"}


def check(directory: str = ".") -> list[Violation]:
    cfg = _load_config()
    root = Path(directory)
    violations: list[Violation] = []

    for path in sorted(root.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        violations.extend(_violations_in_file(path.relative_to(root), content.splitlines(), cfg))

    return violations


def main() -> int:
    violations = check()
    if not violations:
        print("archlint: all checks passed")
        return 0

    for filepath, lineno, rule_id, msg in violations:
        loc = f"{filepath}:{lineno}" if lineno else filepath
        print(f"  {loc}  {rule_id}  {msg}")
    print(f"\narchlint: {len(violations)} violation(s) found")
    return 1


if __name__ == "__main__":
    sys.exit(main())
