#!/usr/bin/env python3
"""Detect stale public symbols masked by local type scaffolding."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from stale_symbol_surfaces_analysis import find_stale_symbol_surface_violations  # noqa: E402
from stale_symbol_surfaces_models import DEFAULT_SCAN_ROOTS, DEFAULT_TARGET_ROOT  # noqa: E402


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
