#!/usr/bin/env python3
"""Validate ast-grep rule YAML structure."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REQUIRED_FIELDS = ("id", "language", "severity", "message", "rule")
MISPLACED_TOP_LEVEL_KEYS = ("constraints", "utils", "transform")


def validate_rule(path: Path) -> list[str]:
    """Return structural validation errors for a rule file."""
    errors: list[str] = []

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"invalid YAML: {exc}"]

    if not isinstance(data, dict):
        return ["rule file must contain a top-level mapping"]

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    rule_node = data.get("rule")
    if isinstance(rule_node, dict):
        for key in MISPLACED_TOP_LEVEL_KEYS:
            if key in rule_node:
                errors.append(f"{key} must be declared at the top level, not inside rule")

    return errors


def main(argv: list[str]) -> int:
    paths = (
        [Path(arg) for arg in argv] if argv else sorted(Path("rules/ast-grep/rules").glob("*.yml"))
    )
    if not paths:
        print("No ast-grep rule files found.")
        return 0

    all_valid = True
    for path in paths:
        errors = validate_rule(path)
        if errors:
            all_valid = False
            print(f"FAIL {path}")
            for error in errors:
                print(f"  - {error}")
            continue
        print(f"OK   {path}")

    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
