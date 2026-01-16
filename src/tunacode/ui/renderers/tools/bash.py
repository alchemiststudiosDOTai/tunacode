"""Slim NeXTSTEP-style panel renderer for bash tool output.

Dream mockup style:
─ bash ──────────────────────────────────────────── ok
  ↳ $ uv run pytest tests/

stdout:
  All tests passed!
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import MIN_VIEWPORT_LINES
from tunacode.ui.renderers.tools.base import (
    tool_renderer,
    truncate_content,
    truncate_line,
)
from tunacode.ui.renderers.tools.slim_base import (
    STYLE_WARNING,
    slim_footer,
    slim_panel,
    styled_line,
)
from tunacode.ui.renderers.tools.syntax_utils import detect_code_lexer, syntax_or_text


@dataclass
class BashData:
    """Parsed bash result for structured display."""

    command: str
    exit_code: int
    working_dir: str
    stdout: str
    stderr: str
    is_truncated: bool
    timeout: int


def parse_bash_result(args: dict[str, Any] | None, result: str) -> BashData | None:
    """Extract structured data from bash output."""
    if not result:
        return None

    command_match = re.search(r"Command: (.+)", result)
    exit_match = re.search(r"Exit Code: (\d+)", result)
    cwd_match = re.search(r"Working Directory: (.+)", result)

    if not command_match or not exit_match:
        return None

    command = command_match.group(1).strip()
    exit_code = int(exit_match.group(1))
    working_dir = cwd_match.group(1).strip() if cwd_match else "."

    stdout = ""
    stderr = ""

    stdout_match = re.search(r"STDOUT:\n(.*?)(?=\n\nSTDERR:|\Z)", result, re.DOTALL)
    if stdout_match:
        stdout = stdout_match.group(1).strip()
        if stdout == "(no output)":
            stdout = ""

    stderr_match = re.search(r"STDERR:\n(.*?)(?:\Z)", result, re.DOTALL)
    if stderr_match:
        stderr = stderr_match.group(1).strip()
        if stderr == "(no errors)":
            stderr = ""

    is_truncated = "[truncated]" in result

    args = args or {}
    timeout = args.get("timeout", 30)

    return BashData(
        command=command,
        exit_code=exit_code,
        working_dir=working_dir,
        stdout=stdout,
        stderr=stderr,
        is_truncated=is_truncated,
        timeout=timeout,
    )


def _detect_output_type(command: str, output: str) -> str | None:
    """Detect lexer from command or output content."""
    cmd_lower = command.lower()

    is_json_cmd = any(x in cmd_lower for x in ["--json", "-j ", "| jq", "curl ", "http"])
    if is_json_cmd and output.strip().startswith(("{", "[")):
        return "json"

    if cmd_lower.startswith(("python", "uv run python", "pytest")):
        return None

    if cmd_lower.startswith("git diff"):
        return "diff"
    if cmd_lower.startswith("git log") and "--format" not in cmd_lower:
        return None

    return detect_code_lexer(output)


@tool_renderer("bash")
def render_bash(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render bash with slim NeXTSTEP panel style.

    Dream mockup format:
    ─ bash ──────────────────────────────────────── ok
      ↳ $ uv run pytest

    stdout:
    All tests passed!
    """
    data = parse_bash_result(args, result)
    if data is None:
        return None

    # Build stats
    stats = "ok" if data.exit_code == 0 else f"exit {data.exit_code}"

    # Subtitle: $ command
    cmd_display = truncate_line(data.command, max_width=50)
    subtitle_text = f"$ {cmd_display}"

    # Build viewport
    viewport_parts: list[RenderableType] = []
    total_lines = 0

    if data.stdout:
        truncated_stdout, _, _ = truncate_content(data.stdout)
        lexer = _detect_output_type(data.command, data.stdout)

        stdout_header = Text("stdout:", style="dim bold")
        viewport_parts.append(stdout_header)

        if lexer:
            viewport_parts.append(syntax_or_text(truncated_stdout, lexer=lexer))
        else:
            viewport_parts.append(Text(truncated_stdout))

        total_lines += len(data.stdout.splitlines())

    if data.stderr:
        if viewport_parts:
            viewport_parts.append(Text(""))

        stderr_header = Text("stderr:", style="dim bold red")
        viewport_parts.append(stderr_header)

        truncated_stderr, _, _ = truncate_content(data.stderr)
        # Show stderr with warning background
        for line in truncated_stderr.splitlines():
            viewport_parts.append(styled_line(line, STYLE_WARNING))

        total_lines += len(data.stderr.splitlines())

    if not viewport_parts:
        viewport_parts.append(Text("(no output)", style="dim italic"))

    # Pad viewport
    lines_used = sum(
        1 + str(p).count("\n") if isinstance(p, Text) else 1 for p in viewport_parts
    )
    while lines_used < MIN_VIEWPORT_LINES:
        viewport_parts.append(Text(""))
        lines_used += 1

    # Footer
    footer = slim_footer(min(total_lines, 8), total_lines)

    viewport = Group(*viewport_parts) if viewport_parts else Text("(no output)", style="dim")

    return slim_panel(
        name="bash",
        content=viewport,
        stats=stats,
        subtitle=subtitle_text,
        footer=footer if str(footer) else None,
    )
