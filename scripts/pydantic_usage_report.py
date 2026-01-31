#!/usr/bin/env python3
"""Generate a pydantic/pydantic_ai usage report and enforce guardrails."""

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
REPORT_GROUPS_KEY = "groups"
REPORT_TOTALS_KEY = "totals"
REPORT_GENERATED_AT_KEY = "generated_at"
REPORT_ROOT_KEY = "root"
REPORT_MATCH_COUNT_KEY = "match_count"
REPORT_FILE_COUNT_KEY = "file_count"
REPORT_FILES_KEY = "files"
REPORT_PATTERN_KEY = "pattern"
REPORT_DESCRIPTION_KEY = "description"
REPORT_NAME_KEY = "name"
FILE_PATH_KEY = "path"
FILE_MATCH_COUNT_KEY = "match_count"

PYDANTIC_AI_IMPORTS_PATTERN = r"\bfrom\s+pydantic_ai\b|\bimport\s+pydantic_ai\b"
PYDANTIC_IMPORTS_PATTERN = r"\bfrom\s+pydantic\b|\bimport\s+pydantic\b"
BASE_MODEL_PATTERN = r"\bBaseModel\b"
FIELD_PATTERN = r"\bField\b"
TYPE_ADAPTER_PATTERN = r"\bTypeAdapter\b"
VALIDATOR_PATTERN = r"\bmodel_validator\b|\bvalidator\b"
AGENT_TOOL_DECORATOR_PATTERN = r"@.*\.tool\b"
AGENT_CALL_PATTERN = r"\bAgent\("
RUN_CONTEXT_PATTERN = r"\bRunContext\b"
REGEX_FLAGS = re.MULTILINE

SCRIPT_DESCRIPTION = "Report pydantic/pydantic_ai usage and enforce guardrails."
ROOT_HELP = "Repository root to scan."
FORMAT_HELP = "Report output format."
OUTPUT_HELP = "Write the report to a file instead of stdout."
BASELINE_HELP = "Baseline JSON report to compare against."
ENFORCE_ZERO_HELP = "Fail if any match count is non-zero."


@dataclass(frozen=True)
class PatternGroup:
    name: str
    description: str
    pattern: str


@dataclass(frozen=True)
class CompiledPatternGroup:
    name: str
    description: str
    pattern: str
    regex: re.Pattern[str]


@dataclass(frozen=True)
class FileMatch:
    path: str
    match_count: int


@dataclass
class PatternGroupReport:
    name: str
    description: str
    pattern: str
    match_count: int = ZERO_COUNT
    files: list[FileMatch] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        sorted_files = sorted(self.files, key=lambda entry: entry.path)
        file_payload = [
            {FILE_PATH_KEY: entry.path, FILE_MATCH_COUNT_KEY: entry.match_count}
            for entry in sorted_files
        ]
        file_count = len(sorted_files)
        return {
            REPORT_NAME_KEY: self.name,
            REPORT_DESCRIPTION_KEY: self.description,
            REPORT_PATTERN_KEY: self.pattern,
            REPORT_MATCH_COUNT_KEY: self.match_count,
            REPORT_FILE_COUNT_KEY: file_count,
            REPORT_FILES_KEY: file_payload,
        }


@dataclass(frozen=True)
class Totals:
    match_count: int
    file_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            REPORT_MATCH_COUNT_KEY: self.match_count,
            REPORT_FILE_COUNT_KEY: self.file_count,
        }


@dataclass(frozen=True)
class UsageReport:
    generated_at: str
    root: str
    groups: list[PatternGroupReport]
    totals: Totals

    def to_dict(self) -> dict[str, object]:
        group_payload = {group.name: group.to_dict() for group in self.groups}
        return {
            REPORT_GENERATED_AT_KEY: self.generated_at,
            REPORT_ROOT_KEY: self.root,
            REPORT_GROUPS_KEY: group_payload,
            REPORT_TOTALS_KEY: self.totals.to_dict(),
        }


def build_pattern_groups() -> list[PatternGroup]:
    return [
        PatternGroup(
            name="pydantic_ai_imports",
            description="Imports that reference pydantic_ai.",
            pattern=PYDANTIC_AI_IMPORTS_PATTERN,
        ),
        PatternGroup(
            name="pydantic_imports",
            description="Imports that reference pydantic.",
            pattern=PYDANTIC_IMPORTS_PATTERN,
        ),
        PatternGroup(
            name="base_model",
            description="BaseModel usage.",
            pattern=BASE_MODEL_PATTERN,
        ),
        PatternGroup(
            name="field",
            description="Field usage.",
            pattern=FIELD_PATTERN,
        ),
        PatternGroup(
            name="type_adapter",
            description="TypeAdapter usage.",
            pattern=TYPE_ADAPTER_PATTERN,
        ),
        PatternGroup(
            name="validator",
            description="validator/model_validator usage.",
            pattern=VALIDATOR_PATTERN,
        ),
        PatternGroup(
            name="agent_tool_decorator",
            description="@agent.tool-style decorators.",
            pattern=AGENT_TOOL_DECORATOR_PATTERN,
        ),
        PatternGroup(
            name="agent_call",
            description="Agent(...) constructor usage.",
            pattern=AGENT_CALL_PATTERN,
        ),
        PatternGroup(
            name="run_context",
            description="RunContext usage.",
            pattern=RUN_CONTEXT_PATTERN,
        ),
    ]


def compile_pattern_groups(groups: Sequence[PatternGroup]) -> list[CompiledPatternGroup]:
    compiled_groups = []
    for group in groups:
        compiled_pattern = re.compile(group.pattern, REGEX_FLAGS)
        compiled_groups.append(
            CompiledPatternGroup(
                name=group.name,
                description=group.description,
                pattern=group.pattern,
                regex=compiled_pattern,
            )
        )
    return compiled_groups


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


def read_text_file(path: Path) -> str:
    return path.read_text(encoding=DEFAULT_ENCODING)


def scan_repository(
    root: Path, compiled_groups: Sequence[CompiledPatternGroup]
) -> list[PatternGroupReport]:
    report_index = {
        group.name: PatternGroupReport(
            name=group.name, description=group.description, pattern=group.pattern
        )
        for group in compiled_groups
    }
    file_paths = list_repo_files(root)
    for path in file_paths:
        if not path.exists():
            continue
        if is_binary_file(path):
            continue
        file_contents = read_text_file(path)
        relative_path = path.relative_to(root)
        relative_path_text = relative_path.as_posix()
        for group in compiled_groups:
            matches = group.regex.findall(file_contents)
            match_count = len(matches)
            if match_count == ZERO_COUNT:
                continue
            report = report_index[group.name]
            report.match_count += match_count
            report.files.append(FileMatch(path=relative_path_text, match_count=match_count))
    reports = list(report_index.values())
    for report in reports:
        report.files.sort(key=lambda entry: entry.path)
    return reports


def compute_totals(groups: Sequence[PatternGroupReport]) -> Totals:
    total_matches = sum(group.match_count for group in groups)
    file_paths = {entry.path for group in groups for entry in group.files}
    total_files = len(file_paths)
    return Totals(match_count=total_matches, file_count=total_files)


def build_usage_report(root: Path, compiled_groups: Sequence[CompiledPatternGroup]) -> UsageReport:
    generated_at = datetime.now(UTC).isoformat()
    group_reports = scan_repository(root, compiled_groups)
    totals = compute_totals(group_reports)
    return UsageReport(
        generated_at=generated_at,
        root=root.as_posix(),
        groups=group_reports,
        totals=totals,
    )


def render_json_report(report: UsageReport) -> str:
    payload = report.to_dict()
    return json.dumps(payload, indent=2)


def render_text_report(report: UsageReport) -> str:
    lines = [
        "Pydantic usage report",
        f"Generated at: {report.generated_at}",
        f"Root: {report.root}",
        SECTION_DIVIDER,
    ]
    for group in report.groups:
        lines.append(group.name)
        lines.append(f"{TEXT_INDENT}Description: {group.description}")
        lines.append(f"{TEXT_INDENT}Pattern: {group.pattern}")
        lines.append(f"{TEXT_INDENT}Match count: {group.match_count}")
        lines.append(f"{TEXT_INDENT}File count: {len(group.files)}")
        lines.append(f"{TEXT_INDENT}Files:")
        if not group.files:
            lines.append(f"{FILE_INDENT}{NO_MATCHES_LABEL}")
            lines.append(GROUP_DIVIDER)
            continue
        for entry in group.files:
            lines.append(f"{FILE_INDENT}- {entry.path} ({entry.match_count})")
        lines.append(GROUP_DIVIDER)
    lines.append("Totals")
    lines.append(f"{TEXT_INDENT}Match count: {report.totals.match_count}")
    lines.append(f"{TEXT_INDENT}File count: {report.totals.file_count}")
    return "\n".join(lines)


def load_report(path: Path) -> dict[str, object]:
    report_text = path.read_text(encoding=DEFAULT_ENCODING)
    report_data = json.loads(report_text)
    if not isinstance(report_data, dict):
        raise ValueError(f"Report at {path} is not a JSON object")
    return report_data


def extract_group_counts(report_data: dict[str, object]) -> dict[str, int]:
    groups_value = report_data.get(REPORT_GROUPS_KEY)
    if not isinstance(groups_value, dict):
        raise ValueError("Report JSON is missing a valid groups mapping")
    counts: dict[str, int] = {}
    for name, group_value in groups_value.items():
        if not isinstance(group_value, dict):
            raise ValueError(f"Group {name} is not a JSON object")
        count_value = group_value.get(REPORT_MATCH_COUNT_KEY)
        if not isinstance(count_value, int):
            raise ValueError(f"Group {name} has an invalid match_count")
        counts[name] = count_value
    return counts


def compare_counts(current: dict[str, int], baseline: dict[str, int]) -> list[str]:
    failures: list[str] = []
    baseline_only = sorted(set(baseline) - set(current))
    if baseline_only:
        missing_groups = ", ".join(baseline_only)
        failures.append(f"Missing groups in current report: {missing_groups}")
    current_only = sorted(set(current) - set(baseline))
    if current_only:
        extra_groups = ", ".join(current_only)
        failures.append(f"Unexpected groups in current report: {extra_groups}")
    for name in sorted(baseline):
        current_count = current.get(name)
        baseline_count = baseline[name]
        if current_count is None:
            continue
        if current_count <= baseline_count:
            continue
        failures.append(f"{name} increased from {baseline_count} to {current_count}")
    return failures


def check_nonzero_counts(current: dict[str, int]) -> list[str]:
    failures: list[str] = []
    for name, count in sorted(current.items()):
        if count == ZERO_COUNT:
            continue
        failures.append(f"{name} is non-zero at {count}")
    return failures


def render_report(report: UsageReport, output_format: str) -> str:
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
    parser.add_argument("--enforce-zero", action="store_true", help=ENFORCE_ZERO_HELP)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root_path = Path(args.root)
    if not root_path.exists():
        raise FileNotFoundError(f"Root path does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Root path is not a directory: {root_path}")

    pattern_groups = build_pattern_groups()
    compiled_groups = compile_pattern_groups(pattern_groups)

    report = build_usage_report(root_path, compiled_groups)
    report_text = render_report(report, args.format)
    write_report(report_text, args.output)

    report_data = report.to_dict()
    current_counts = extract_group_counts(report_data)

    failures: list[str] = []
    if args.baseline is not None:
        baseline_path = args.baseline
        baseline_report = load_report(baseline_path)
        baseline_counts = extract_group_counts(baseline_report)
        failures.extend(compare_counts(current_counts, baseline_counts))
    if args.enforce_zero:
        failures.extend(check_nonzero_counts(current_counts))

    if not failures:
        return EXIT_SUCCESS

    print("Pydantic usage guard failed:", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
