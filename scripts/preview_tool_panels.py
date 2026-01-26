#!/usr/bin/env python3
from __future__ import annotations

import argparse
import textwrap
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from rich.console import Console

from tunacode.constants import MIN_TOOL_PANEL_LINE_WIDTH, TOOL_PANEL_HORIZONTAL_INSET

from tunacode.ui.renderers.panels import tool_panel_smart

DEFAULT_WIDTH = 92
DEFAULT_DURATION_MS = 128.0
ERROR_DURATION_MS = 412.0
DEFAULT_MAX_FILES = 100
DEFAULT_TIMEOUT_SECONDS = 30
WEB_FETCH_TIMEOUT_SECONDS = 20
DEFAULT_CONTEXT_LINES = 2
RESEARCH_DIRECTORIES_DISPLAY = ["src/tunacode/ui"]
LIST_DIR_IGNORE_PATTERNS = [".git", ".venv"]

FILE_ICON = "\U0001f4c1"
MATCH_MARKER = "\u25b6"
MATCH_LANGLE = "\u27e8"
MATCH_RANGLE = "\u27e9"

LIST_DIR_FILES = 7
LIST_DIR_DIRS = 3
LIST_DIR_TRUNCATED_FILES = 120
LIST_DIR_TRUNCATED_DIRS = 24

GREP_MATCHES = 3
GREP_CANDIDATES = 18
GREP_LINE_ONE = 42
GREP_LINE_TWO = 57
GREP_LINE_THREE = 103

GLOB_FILES = 4
GLOB_TRUNCATED_FILES = 32

READ_FILE_TOTAL = 120
READ_FILE_END_LINES = 4
READ_FILE_OFFSET = 0

BASH_SUCCESS_EXIT = 0
BASH_ERROR_EXIT = 2

RESEARCH_MAX_FILES = 4


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    tool_name: str
    status: str
    args: dict[str, Any] | None
    result: str | None
    duration_ms: float | None


def _dedent(text: str) -> str:
    return textwrap.dedent(text).strip()


def build_list_dir_result(truncated: bool) -> str:
    files = LIST_DIR_TRUNCATED_FILES if truncated else LIST_DIR_FILES
    dirs = LIST_DIR_TRUNCATED_DIRS if truncated else LIST_DIR_DIRS
    truncated_suffix = " (truncated)" if truncated else ""
    header_line = f"{files} files  {dirs} dirs{truncated_suffix}"

    tree = _dedent(
        """
        /root/tunacode/
        ├── src/
        │  ├── tunacode/
        │  │  ├── ui/
        │  │  └── tools/
        │  └── tests/
        ├── README.md
        └── pyproject.toml
        """
    )

    return f"{header_line}\n{tree}"


def build_grep_result() -> str:
    header = f"Found {GREP_MATCHES} matches for pattern: panel"
    strategy_line = f"Strategy: smart | Candidates: {GREP_CANDIDATES} files | case: no"
    file_header = f"{FILE_ICON} src/tunacode/ui/renderers/tools/base.py:{GREP_LINE_ONE}"

    match_one = f"{MATCH_MARKER} {GREP_LINE_ONE}│ return {MATCH_LANGLE}Panel{MATCH_RANGLE}("
    match_two = f'{MATCH_MARKER} {GREP_LINE_TWO}│ title=f"[{MATCH_LANGLE}border{MATCH_RANGLE}]"'
    second_file = f"{FILE_ICON} src/tunacode/ui/renderers/panels.py:{GREP_LINE_THREE}"
    match_three = f"{MATCH_MARKER} {GREP_LINE_THREE}│ def tool_{MATCH_LANGLE}panel{MATCH_RANGLE}("

    result_lines = [
        header,
        strategy_line,
        file_header,
        match_one,
        match_two,
        second_file,
        match_three,
    ]
    return "\n".join(result_lines)


def build_glob_result(truncated: bool) -> str:
    source_line = "[source:index]"
    count = GLOB_TRUNCATED_FILES if truncated else GLOB_FILES
    header_line = f"Found {count} files matching pattern: **/*.py"
    files = [
        "src/tunacode/ui/renderers/tools/base.py",
        "src/tunacode/ui/renderers/tools/bash.py",
        "src/tunacode/ui/renderers/tools/read_file.py",
        "src/tunacode/ui/renderers/tools/update_file.py",
    ]
    truncated_line = f"(truncated at {GLOB_TRUNCATED_FILES})" if truncated else ""

    file_block = "\n".join(files)
    if truncated_line:
        file_block = f"{file_block}\n{truncated_line}"

    return "\n".join([source_line, header_line, "", file_block])


def build_read_file_result(has_more: bool) -> str:
    content_lines = [
        "00001| from tunacode.ui.renderers.panels import tool_panel_smart",
        "00002| ",
        "00003| def on_tool_result_display(message):",
        "00004|     panel = tool_panel_smart(...)",
    ]
    total_line_count = READ_FILE_TOTAL
    end_line_count = READ_FILE_END_LINES
    footer = (
        f"(File has more lines. Use 'offset' to read beyond line {total_line_count})"
        if has_more
        else f"(End of file - total {end_line_count} lines)"
    )
    body = "\n".join(content_lines + [footer])
    return f"<file>\n{body}\n</file>"


def build_update_file_result(with_diagnostics: bool) -> str:
    message = "File 'src/tunacode/ui/renderers/tools/base.py' updated successfully."
    diff = _dedent(
        """
        --- a/src/tunacode/ui/renderers/tools/base.py
        +++ b/src/tunacode/ui/renderers/tools/base.py
        @@ -401,9 +401,7 @@ def render(
        -        content_parts: list[RenderableType] = [
        -            header,
        -            Text("\\n"),
        -        ]
        +        content_parts: list[RenderableType] = [header]
        """
    )
    diagnostics = ""
    if with_diagnostics:
        diagnostics = _dedent(
            """
            <file_diagnostics>
            Warning (line 401): unused import
            </file_diagnostics>
            """
        )

    return "\n\n".join(part for part in [message, diff, diagnostics] if part)


def build_bash_result(exit_code: int) -> str:
    command = 'rg -n "tool_panel_smart" src'
    header = (
        "Command: {command}\n"
        "Exit Code: {exit_code}\n"
        "Working Directory: /root/tunacode\n\n"
        "STDOUT:\n"
        "{stdout}\n\n"
        "STDERR:\n"
        "{stderr}"
    )

    is_success = exit_code == 0
    stdout = (
        "src/tunacode/ui/renderers/panels.py:476: def tool_panel_smart("
        if is_success
        else "(no output)"
    )
    stderr = "(no errors)" if is_success else "rg: warning: file is binary"

    formatted = header.format(command=command, exit_code=exit_code, stdout=stdout, stderr=stderr)
    return formatted


def build_web_fetch_result(truncated: bool) -> str:
    headline = "<html><head><title>TunaCode</title></head>"
    body = "<body><h1>Tool Panel Preview</h1><p>Sample content.</p></body></html>"
    content = f"{headline}\n{body}"
    if truncated:
        content = f"{content}\n[Content truncated due to size]"
    return content


def build_research_result() -> str:
    return _dedent(
        """
        {
            "relevant_files": [
                "src/tunacode/ui/renderers/panels.py",
                "src/tunacode/ui/renderers/tools/base.py"
            ],
            "key_findings": [
                "tool_panel_smart routes completed tool output to renderers.",
                "BaseToolRenderer builds a 4-zone layout with separators."
            ],
            "code_examples": [
                {
                    "file": "src/tunacode/ui/renderers/tools/base.py",
                    "code": "def render(...):\\n    content = Group(...)",
                    "explanation": "Template method orchestrating tool panels."
                }
            ],
            "recommendations": [
                "Add preview script for tool panels.",
                "Reduce vertical padding for compact layouts."
            ]
        }
        """
    )


def build_scenarios() -> list[Scenario]:
    list_dir_args = {
        "max_files": DEFAULT_MAX_FILES,
        "show_hidden": False,
        "ignore": LIST_DIR_IGNORE_PATTERNS,
    }
    grep_args = {
        "pattern": "panel",
        "case_sensitive": False,
        "use_regex": False,
        "context_lines": DEFAULT_CONTEXT_LINES,
    }
    glob_args = {
        "pattern": "**/*.py",
        "recursive": True,
        "include_hidden": False,
        "sort_by": "modified",
    }
    read_file_args = {"filepath": "src/tunacode/ui/renderers/panels.py", "offset": READ_FILE_OFFSET}
    update_file_args = {"filepath": "src/tunacode/ui/renderers/tools/base.py"}
    bash_args = {"command": 'rg -n "tool_panel_smart" src', "timeout": DEFAULT_TIMEOUT_SECONDS}
    web_fetch_args = {
        "url": "https://example.com/docs/tool-panel",
        "timeout": WEB_FETCH_TIMEOUT_SECONDS,
    }
    research_args = {
        "query": "tool panel architecture",
        "directories": RESEARCH_DIRECTORIES_DISPLAY,
        "max_files": RESEARCH_MAX_FILES,
    }
    error_args = {"note": "fallback renderer"}

    return [
        Scenario(
            name="list_dir-basic",
            description="Standard directory listing",
            tool_name="list_dir",
            status="completed",
            args=list_dir_args,
            result=build_list_dir_result(truncated=False),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="list_dir-truncated",
            description="Directory listing with truncation",
            tool_name="list_dir",
            status="completed",
            args=list_dir_args,
            result=build_list_dir_result(truncated=True),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="grep-basic",
            description="Multiple matches across files",
            tool_name="grep",
            status="completed",
            args=grep_args,
            result=build_grep_result(),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="glob-basic",
            description="Glob results from index",
            tool_name="glob",
            status="completed",
            args=glob_args,
            result=build_glob_result(truncated=False),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="glob-truncated",
            description="Glob results truncated",
            tool_name="glob",
            status="completed",
            args=glob_args,
            result=build_glob_result(truncated=True),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="read_file-basic",
            description="Read file complete output",
            tool_name="read_file",
            status="completed",
            args=read_file_args,
            result=build_read_file_result(has_more=False),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="read_file-more",
            description="Read file with more content available",
            tool_name="read_file",
            status="completed",
            args=read_file_args,
            result=build_read_file_result(has_more=True),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="update_file-basic",
            description="Update file diff",
            tool_name="update_file",
            status="completed",
            args=update_file_args,
            result=build_update_file_result(with_diagnostics=False),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="update_file-diagnostics",
            description="Update file with diagnostics",
            tool_name="update_file",
            status="completed",
            args=update_file_args,
            result=build_update_file_result(with_diagnostics=True),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="bash-success",
            description="Command with stdout",
            tool_name="bash",
            status="completed",
            args=bash_args,
            result=build_bash_result(exit_code=BASH_SUCCESS_EXIT),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="bash-error",
            description="Command with stderr",
            tool_name="bash",
            status="completed",
            args=bash_args,
            result=build_bash_result(exit_code=BASH_ERROR_EXIT),
            duration_ms=ERROR_DURATION_MS,
        ),
        Scenario(
            name="web_fetch-html",
            description="Web fetch HTML content",
            tool_name="web_fetch",
            status="completed",
            args=web_fetch_args,
            result=build_web_fetch_result(truncated=False),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="web_fetch-truncated",
            description="Web fetch truncated content",
            tool_name="web_fetch",
            status="completed",
            args=web_fetch_args,
            result=build_web_fetch_result(truncated=True),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="research-basic",
            description="Research tool structured output",
            tool_name="research_codebase",
            status="completed",
            args=research_args,
            result=build_research_result(),
            duration_ms=DEFAULT_DURATION_MS,
        ),
        Scenario(
            name="tool-error",
            description="Fallback renderer for tool error",
            tool_name="unknown_tool",
            status="error",
            args=error_args,
            result="Tool failed: permission denied",
            duration_ms=ERROR_DURATION_MS,
        ),
    ]


def select_scenarios(scenarios: Iterable[Scenario], names: list[str]) -> list[Scenario]:
    selected: list[Scenario] = []
    names_set = set(names)
    for scenario in scenarios:
        if scenario.name in names_set:
            selected.append(scenario)
    return selected


def ensure_known_scenarios(all_scenarios: Iterable[Scenario], names: list[str]) -> None:
    known = {scenario.name for scenario in all_scenarios}
    unknown = [name for name in names if name not in known]
    if unknown:
        joined = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown scenarios: {joined}")


def print_scenarios(scenarios: Iterable[Scenario]) -> None:
    for scenario in scenarios:
        print(f"{scenario.name} - {scenario.description}")


def render_scenarios(console: Console, scenarios: Iterable[Scenario]) -> None:
    available_width = console.width - TOOL_PANEL_HORIZONTAL_INSET
    max_line_width = max(MIN_TOOL_PANEL_LINE_WIDTH, available_width)
    for scenario in scenarios:
        console.rule(f"{scenario.name} - {scenario.description}")
        panel = tool_panel_smart(
            scenario.tool_name,
            scenario.status,
            args=scenario.args,
            result=scenario.result,
            duration_ms=scenario.duration_ms,
            max_line_width=max_line_width,
        )
        console.print(panel)
        console.print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview tool panel renderers.")
    parser.add_argument("--list", action="store_true", help="List available scenarios and exit.")
    parser.add_argument("--all", action="store_true", help="Render all scenarios.")
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario name to render (repeatable).",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help="Console width for rendering.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenarios = build_scenarios()

    if args.list:
        print_scenarios(scenarios)
        return 0

    requested_names = list(args.scenario)
    use_all = args.all or not requested_names

    if not use_all:
        ensure_known_scenarios(scenarios, requested_names)
        scenarios = select_scenarios(scenarios, requested_names)

    console_width = args.width
    console = Console(width=console_width, force_terminal=True)
    render_scenarios(console, scenarios)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
