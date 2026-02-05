#!/usr/bin/env python3
"""Scan for TODO/FIXME comments and track technical debt."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

DEFAULT_ENCODING = "utf-8"
DEFAULT_FORMAT = "json"
FORMAT_JSON = "json"
FORMAT_TEXT = "text"
SUPPORTED_FORMATS = (FORMAT_JSON, FORMAT_TEXT)
DEFAULT_ROOT = Path(".")
GIT_LS_FILES_COMMAND = ("git", "ls-files")
BINARY_SNIFF_SIZE = 1024
NULL_BYTE = b"\x00"
TEXT_SECTION_WIDTH = 72
SECTION_DIVIDER = "=" * TEXT_SECTION_WIDTH
GROUP_DIVIDER = "-" * TEXT_SECTION_WIDTH
TEXT_INDENT = "  "
FILE_INDENT = f"{TEXT_INDENT}{TEXT_INDENT}"
NO_MATCHES_LABEL = "(none)"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
ZERO_COUNT = 0

REPORT_ITEMS_KEY = "items"
REPORT_TOTALS_KEY = "totals"
REPORT_GENERATED_AT_KEY = "generated_at"
REPORT_ROOT_KEY = "root"
REPORT_COUNT_KEY = "count"
REPORT_FILES_KEY = "files"
REPORT_FILE_COUNT_KEY = "file_count"
REPORT_TYPE_KEY = "type"
REPORT_LINE_KEY = "line"
REPORT_COLUMN_KEY = "column"
REPORT_CONTENT_KEY = "content"
REPORT_PATH_KEY = "path"

SCRIPT_DESCRIPTION = "Scan for TODO/FIXME comments and track technical debt."
ROOT_HELP = "Repository root to scan."
FORMAT_HELP = "Report output format."
OUTPUT_HELP = "Write the report to a file instead of stdout."
BASELINE_HELP = "Baseline JSON report to compare against."
FAIL_ON_INCREASE_HELP = "Fail if TODO/FIXME count increased from baseline."
FAIL_ON_NEW_HELP = "Fail if new TODO/FIXME items are found (any count > 0)."
INCLUDE_TESTS_HELP = "Include test files in the scan."

TODO_PATTERN = r"TODO\s*\([^)]*\)\s*:?\s*(.+)"
FIXME_PATTERN = r"FIXME\s*\([^)]*\)\s*:?\s*(.+)"
HACK_PATTERN = r"HACK\s*\([^)]*\)\s*:?\s*(.+)"
XXX_PATTERN = r"XXX\s*\([^)]*\)\s*:?\s*(.+)?"
REGEX_FLAGS = re.IGNORECASE | re.MULTILINE

EXCLUDE_PATTERNS = [
    r"^\.git/",
    r"\.pyc$",
    r"\.md$",
    r"__pycache__/",
    r"\.venv/",
    r"node_modules/",
    r"\.tox/",
    r"build/",
    r"dist/",
    r"\.egg-info/",
    r"^pyproject\.toml$",
    r"^\.pre-commit-config\.yaml$",
]

TEST_PATTERNS = [
    r"^tests?/",
    r"_test\.py$",
    r"^test_",
]


@dataclass(frozen=True)
class DebtItem:
    type: str
    path: str
    line: int
    column: int
    content: str

    DEBT_TYPE_TODO: ClassVar[str] = "TODO"
    DEBT_TYPE_FIXME: ClassVar[str] = "FIXME"
    DEBT_TYPE_HACK: ClassVar[str] = "HACK"
    DEBT_TYPE_XXX: ClassVar[str] = "XXX"

    def to_dict(self) -> dict[str, object]:
        return {
            REPORT_TYPE_KEY: self.type,
            REPORT_PATH_KEY: self.path,
            REPORT_LINE_KEY: self.line,
            REPORT_COLUMN_KEY: self.column,
            REPORT_CONTENT_KEY: self.content,
        }


@dataclass(frozen=True)
class FileReport:
    path: str
    items: list[DebtItem]

    @property
    def count(self) -> int:
        return len(self.items)


@dataclass
class DebtTypeReport:
    debt_type: str
    count: int = ZERO_COUNT
    files: list[FileReport] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            REPORT_COUNT_KEY: self.count,
            REPORT_FILE_COUNT_KEY: len(self.files),
            REPORT_FILES_KEY: [
                {
                    REPORT_PATH_KEY: file_report.path,
                    REPORT_COUNT_KEY: file_report.count,
                    REPORT_ITEMS_KEY: [item.to_dict() for item in file_report.items],
                }
                for file_report in sorted(self.files, key=lambda f: f.path)
            ],
        }


@dataclass(frozen=True)
class Totals:
    todo_count: int
    fixme_count: int
    hack_count: int
    xxx_count: int
    total_count: int
    file_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "todo_count": self.todo_count,
            "fixme_count": self.fixme_count,
            "hack_count": self.hack_count,
            "xxx_count": self.xxx_count,
            "total_count": self.total_count,
            "file_count": self.file_count,
        }


@dataclass(frozen=True)
class DebtReport:
    generated_at: str
    root: str
    todo: DebtTypeReport
    fixme: DebtTypeReport
    hack: DebtTypeReport
    xxx: DebtTypeReport
    totals: Totals

    def to_dict(self) -> dict[str, object]:
        return {
            REPORT_GENERATED_AT_KEY: self.generated_at,
            REPORT_ROOT_KEY: self.root,
            "todo": self.todo.to_dict(),
            "fixme": self.fixme.to_dict(),
            "hack": self.hack.to_dict(),
            "xxx": self.xxx.to_dict(),
            REPORT_TOTALS_KEY: self.totals.to_dict(),
        }


def build_debt_patterns() -> dict[str, re.Pattern[str]]:
    return {
        DebtItem.DEBT_TYPE_TODO: re.compile(TODO_PATTERN, REGEX_FLAGS),
        DebtItem.DEBT_TYPE_FIXME: re.compile(FIXME_PATTERN, REGEX_FLAGS),
        DebtItem.DEBT_TYPE_HACK: re.compile(HACK_PATTERN, REGEX_FLAGS),
        DebtItem.DEBT_TYPE_XXX: re.compile(XXX_PATTERN, REGEX_FLAGS),
    }


def should_exclude_path(path: str, include_tests: bool) -> bool:
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, path):
            return True
    if not include_tests:
        for pattern in TEST_PATTERNS:
            if re.search(pattern, path):
                return True
    return False


def list_repo_files(root: Path) -> list[Path]:
    result = subprocess.run(
        GIT_LS_FILES_COMMAND,
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    raw_paths = result.stdout.splitlines()
    return [root / path for path in raw_paths if path]


def is_binary_file(path: Path) -> bool:
    with path.open("rb") as handle:
        sample = handle.read(BINARY_SNIFF_SIZE)
    return NULL_BYTE in sample


def scan_file(
    path: Path,
    relative_path: str,
    patterns: dict[str, re.Pattern[str]],
) -> list[DebtItem]:
    items: list[DebtItem] = []
    try:
        content = path.read_text(encoding=DEFAULT_ENCODING)
    except (UnicodeDecodeError, OSError):
        return items

    lines = content.splitlines()
    for line_num, line_content in enumerate(lines, start=1):
        for debt_type, pattern in patterns.items():
            for match in pattern.finditer(line_content):
                column = match.start() + 1
                matched_text = match.group(1).strip() if match.groups() else line_content.strip()
                items.append(
                    DebtItem(
                        type=debt_type,
                        path=relative_path,
                        line=line_num,
                        column=column,
                        content=matched_text,
                    )
                )
    return items


def scan_repository(
    root: Path,
    patterns: dict[str, re.Pattern[str]],
    include_tests: bool,
) -> DebtReport:
    generated_at = datetime.now(UTC).isoformat()
    file_paths = list_repo_files(root)

    all_items: list[DebtItem] = []
    scanned_files: set[str] = set()

    for path in file_paths:
        relative_path = path.relative_to(root).as_posix()
        if should_exclude_path(relative_path, include_tests):
            continue
        if not path.is_file():
            continue
        if is_binary_file(path):
            continue

        items = scan_file(path, relative_path, patterns)
        if items:
            all_items.extend(items)
            scanned_files.add(relative_path)

    todo_items = [i for i in all_items if i.type == DebtItem.DEBT_TYPE_TODO]
    fixme_items = [i for i in all_items if i.type == DebtItem.DEBT_TYPE_FIXME]
    hack_items = [i for i in all_items if i.type == DebtItem.DEBT_TYPE_HACK]
    xxx_items = [i for i in all_items if i.type == DebtItem.DEBT_TYPE_XXX]

    todo_report = build_type_report(DebtItem.DEBT_TYPE_TODO, todo_items)
    fixme_report = build_type_report(DebtItem.DEBT_TYPE_FIXME, fixme_items)
    hack_report = build_type_report(DebtItem.DEBT_TYPE_HACK, hack_items)
    xxx_report = build_type_report(DebtItem.DEBT_TYPE_XXX, xxx_items)

    totals = Totals(
        todo_count=len(todo_items),
        fixme_count=len(fixme_items),
        hack_count=len(hack_items),
        xxx_count=len(xxx_items),
        total_count=len(all_items),
        file_count=len(scanned_files),
    )

    return DebtReport(
        generated_at=generated_at,
        root=root.as_posix(),
        todo=todo_report,
        fixme=fixme_report,
        hack=hack_report,
        xxx=xxx_report,
        totals=totals,
    )


def build_type_report(debt_type: str, items: list[DebtItem]) -> DebtTypeReport:
    files_dict: dict[str, list[DebtItem]] = {}
    for item in items:
        if item.path not in files_dict:
            files_dict[item.path] = []
        files_dict[item.path].append(item)

    file_reports = [
        FileReport(path=path, items=sorted(items, key=lambda i: i.line))
        for path, items in files_dict.items()
    ]

    return DebtTypeReport(
        debt_type=debt_type,
        count=len(items),
        files=sorted(file_reports, key=lambda f: f.path),
    )


def render_json_report(report: DebtReport) -> str:
    payload = report.to_dict()
    return json.dumps(payload, indent=2)


def render_text_report(report: DebtReport) -> str:
    lines = [
        "Technical Debt Report",
        f"Generated at: {report.generated_at}",
        f"Root: {report.root}",
        SECTION_DIVIDER,
        "",
        f"TODOs: {report.totals.todo_count}",
        f"FIXMEs: {report.totals.fixme_count}",
        f"HACKs: {report.totals.hack_count}",
        f"XXXs: {report.totals.xxx_count}",
        f"Total: {report.totals.total_count} items in {report.totals.file_count} files",
        "",
        SECTION_DIVIDER,
    ]

    for type_report in (report.todo, report.fixme, report.hack, report.xxx):
        if type_report.count == 0:
            continue
        lines.append(f"\n{type_report.debt_type} ({type_report.count})")
        lines.append(GROUP_DIVIDER)
        for file_report in type_report.files:
            lines.append(f"\n{TEXT_INDENT}{file_report.path}")
            for item in file_report.items:
                lines.append(f"{FILE_INDENT}Line {item.line}: {item.content[:60]}")

    return "\n".join(lines)


def load_report(path: Path) -> dict[str, object]:
    report_text = path.read_text(encoding=DEFAULT_ENCODING)
    report_data = json.loads(report_text)
    if not isinstance(report_data, dict):
        raise ValueError(f"Report at {path} is not a JSON object")
    return report_data


def extract_totals(report_data: dict[str, object]) -> dict[str, int]:
    totals_value = report_data.get(REPORT_TOTALS_KEY)
    if not isinstance(totals_value, dict):
        raise ValueError("Report JSON is missing valid totals")
    return {
        "total": totals_value.get("total_count", 0),
        "todo": totals_value.get("todo_count", 0),
        "fixme": totals_value.get("fixme_count", 0),
        "hack": totals_value.get("hack_count", 0),
        "xxx": totals_value.get("xxx_count", 0),
    }


def compare_with_baseline(
    current: dict[str, int],
    baseline: dict[str, int],
) -> list[str]:
    failures: list[str] = []
    for key in ("total", "todo", "fixme", "hack", "xxx"):
        current_val = current.get(key, 0)
        baseline_val = baseline.get(key, 0)
        if current_val > baseline_val:
            failures.append(
                f"{key.upper()}: {baseline_val} -> {current_val} (+{current_val - baseline_val})"
            )
    return failures


def render_report(report: DebtReport, output_format: str) -> str:
    if output_format == FORMAT_TEXT:
        return render_text_report(report)
    return render_json_report(report)


def write_report(report_text: str, output_path: Path | None) -> None:
    if output_path is None:
        print(report_text)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding=DEFAULT_ENCODING)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=SCRIPT_DESCRIPTION)
    parser.add_argument("--root", default=DEFAULT_ROOT, help=ROOT_HELP)
    parser.add_argument(
        "--format", choices=SUPPORTED_FORMATS, default=DEFAULT_FORMAT, help=FORMAT_HELP
    )
    parser.add_argument("--output", type=Path, help=OUTPUT_HELP)
    parser.add_argument("--baseline", type=Path, help=BASELINE_HELP)
    parser.add_argument("--fail-on-increase", action="store_true", help=FAIL_ON_INCREASE_HELP)
    parser.add_argument("--fail-on-new", action="store_true", help=FAIL_ON_NEW_HELP)
    parser.add_argument("--include-tests", action="store_true", help=INCLUDE_TESTS_HELP)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root_path = Path(args.root)
    if not root_path.exists():
        raise FileNotFoundError(f"Root path does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Root path is not a directory: {root_path}")

    patterns = build_debt_patterns()
    report = scan_repository(root_path, patterns, args.include_tests)
    report_text = render_report(report, args.format)
    write_report(report_text, args.output)

    current_totals = extract_totals(report.to_dict())
    failures: list[str] = []

    if args.baseline is not None:
        baseline_path = args.baseline
        baseline_report = load_report(baseline_path)
        baseline_totals = extract_totals(baseline_report)
        increase_failures = compare_with_baseline(current_totals, baseline_totals)
        if increase_failures and args.fail_on_increase:
            failures.extend(increase_failures)

    if args.fail_on_new and current_totals["total"] > 0:
        failures.append(f"Found {current_totals['total']} new debt items")

    if not failures:
        return EXIT_SUCCESS

    print("Technical debt check failed:", file=sys.stderr)
    for failure in failures:
        print(f"  - {failure}", file=sys.stderr)
    return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
