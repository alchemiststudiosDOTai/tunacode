#!/usr/bin/env python3
"""Ratchet ast-grep findings against a committed baseline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

CONFIG_PATH = Path("rules/ast-grep/sgconfig.yml")
BASELINE_PATH = Path("rules/ast-grep/baseline/no-getattr-in-src.json")
SCAN_COMMAND = [
    "npx",
    "--yes",
    "--package",
    "@ast-grep/cli",
    "ast-grep",
    "scan",
    "--config",
    str(CONFIG_PATH),
    "--json=compact",
    "src",
]


def _run_scan() -> list[dict[str, object]]:
    result = subprocess.run(
        SCAN_COMMAND,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        sys.stderr.write(result.stderr)
        raise RuntimeError("ast-grep scan failed")
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"could not parse ast-grep JSON: {exc}") from exc


def _normalize_findings(findings: list[dict[str, object]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for finding in findings:
        normalized.append(
            {
                "rule_id": str(finding["ruleId"]),
                "file": str(finding["file"]),
                "text": str(finding["text"]),
            }
        )
    normalized.sort(key=lambda item: (item["file"], item["text"], item["rule_id"]))
    return normalized


def _load_baseline() -> list[dict[str, str]]:
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(f"missing baseline: {BASELINE_PATH}")
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("baseline must be a JSON list")
    return [
        {
            "rule_id": str(item["rule_id"]),
            "file": str(item["file"]),
            "text": str(item["text"]),
        }
        for item in data
    ]


def _counter(items: list[dict[str, str]]) -> Counter[tuple[str, str, str]]:
    return Counter((item["rule_id"], item["file"], item["text"]) for item in items)


def _write_baseline() -> int:
    findings = _normalize_findings(_run_scan())
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(findings)} ast-grep baseline entries to {BASELINE_PATH}")
    return 0


def _check_baseline() -> int:
    current = _normalize_findings(_run_scan())
    baseline = _load_baseline()

    current_counter = _counter(current)
    baseline_counter = _counter(baseline)

    new_entries: list[dict[str, str]] = []
    for item in current:
        key = (item["rule_id"], item["file"], item["text"])
        if baseline_counter[key] > 0:
            baseline_counter[key] -= 1
            continue
        new_entries.append(item)

    if new_entries:
        print("New ast-grep getattr findings not present in baseline:")
        for item in new_entries:
            print(f"- {item['file']}: {item['text']}")
        print(f"Baseline file: {BASELINE_PATH}")
        return 1

    removed_count = sum((current_counter - _counter(baseline)).values())
    if removed_count < 0:
        removed_count = 0
    print(f"Ast-grep baseline check passed ({len(current)} current findings, no new violations).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    if args.write_baseline:
        return _write_baseline()
    return _check_baseline()


if __name__ == "__main__":
    raise SystemExit(main())
