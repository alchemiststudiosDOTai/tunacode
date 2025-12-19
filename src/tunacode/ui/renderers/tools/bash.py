"""NeXTSTEP-style panel renderer for bash tool output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from tunacode.constants import (
    MAX_PANEL_LINE_WIDTH,
    MIN_VIEWPORT_LINES,
    TOOL_VIEWPORT_LINES,
    UI_COLORS,
)

BOX_HORIZONTAL = "\u2500"
SEPARATOR_WIDTH = 52


@dataclass
class BashData:
    """Parsed bash result for structured display."""

    command: str
    exit_code: int
    working_dir: str
    stdout: str
    stderr: str
    is_truncated: bool


def parse_result(args: dict[str, Any] | None, result: str) -> BashData | None:
    """Extract structured data from bash output.

    Expected format:
        Command: <command>
        Exit Code: <code>
        Working Directory: <path>

        STDOUT:
        <output>

        STDERR:
        <errors>
    """
    if not result:
        return None

    # Parse structured output
    command_match = re.search(r"Command: (.+)", result)
    exit_match = re.search(r"Exit Code: (\d+)", result)
    cwd_match = re.search(r"Working Directory: (.+)", result)

    if not command_match or not exit_match:
        return None

    command = command_match.group(1).strip()
    exit_code = int(exit_match.group(1))
    working_dir = cwd_match.group(1).strip() if cwd_match else "."

    # Extract stdout and stderr
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

    # Check for truncation marker
    is_truncated = "[truncated]" in result

    return BashData(
        command=command,
        exit_code=exit_code,
        working_dir=working_dir,
        stdout=stdout,
        stderr=stderr,
        is_truncated=is_truncated,
    )


def _truncate_line(line: str) -> str:
    """Truncate a single line if too wide."""
    if len(line) > MAX_PANEL_LINE_WIDTH:
        return line[: MAX_PANEL_LINE_WIDTH - 3] + "..."
    return line


def _truncate_output(output: str) -> tuple[str, int, int]:
    """Truncate output, return (truncated, shown, total)."""
    lines = output.splitlines()
    total = len(lines)

    max_lines = TOOL_VIEWPORT_LINES

    if total <= max_lines:
        return "\n".join(_truncate_line(ln) for ln in lines), total, total

    truncated = [_truncate_line(ln) for ln in lines[:max_lines]]
    return "\n".join(truncated), max_lines, total


def render_bash(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None = None,
) -> RenderableType | None:
    """Render bash with NeXTSTEP zoned layout.

    Zones:
    - Header: command + exit code indicator
    - Selection context: working directory, timeout
    - Primary viewport: stdout/stderr output
    - Status: truncation info, duration
    """
    data = parse_result(args, result)
    if not data:
        return None

    # Zone 1: Command + exit status
    header = Text()

    # Truncate command for header
    cmd_display = data.command
    if len(cmd_display) > 50:
        cmd_display = cmd_display[:47] + "..."
    header.append(f"$ {cmd_display}", style="bold")

    # Exit code indicator
    if data.exit_code == 0:
        header.append("   ", style="")
        header.append("ok", style="green bold")
    else:
        header.append("   ", style="")
        header.append(f"exit {data.exit_code}", style="red bold")

    # Zone 2: Parameters
    args = args or {}
    timeout = args.get("timeout", 30)
    params = Text()
    params.append("cwd:", style="dim")
    params.append(f" {data.working_dir}", style="dim bold")
    params.append("  timeout:", style="dim")
    params.append(f" {timeout}s", style="dim bold")

    separator = Text(BOX_HORIZONTAL * SEPARATOR_WIDTH, style="dim")

    # Zone 3: Output viewport
    viewport_parts: list[Text] = []

    if data.stdout:
        truncated_stdout, shown_stdout, total_stdout = _truncate_output(data.stdout)
        stdout_text = Text()
        stdout_text.append("stdout:\n", style="dim")
        stdout_text.append(truncated_stdout)
        viewport_parts.append(stdout_text)

    if data.stderr:
        if viewport_parts:
            viewport_parts.append(Text("\n"))
        truncated_stderr, shown_stderr, total_stderr = _truncate_output(data.stderr)
        stderr_text = Text()
        stderr_text.append("stderr:\n", style="dim")
        stderr_text.append(truncated_stderr, style="red")
        viewport_parts.append(stderr_text)

    if not viewport_parts:
        viewport_parts.append(Text("(no output)", style="dim"))

    # Pad viewport to minimum height for visual consistency
    viewport_line_count = sum(
        1 + str(part).count("\n") for part in viewport_parts if isinstance(part, Text)
    )
    while viewport_line_count < MIN_VIEWPORT_LINES:
        viewport_parts.append(Text(""))
        viewport_line_count += 1

    viewport = Group(*viewport_parts)

    # Zone 4: Status
    status_items: list[str] = []

    if data.is_truncated:
        status_items.append("(truncated)")

    if data.stdout:
        stdout_lines = len(data.stdout.splitlines())
        status_items.append(f"stdout: {stdout_lines} lines")

    if data.stderr:
        stderr_lines = len(data.stderr.splitlines())
        status_items.append(f"stderr: {stderr_lines} lines")

    if duration_ms is not None:
        status_items.append(f"{duration_ms:.0f}ms")

    status = Text("  ".join(status_items), style="dim") if status_items else Text("")

    # Compose
    content = Group(
        header,
        Text("\n"),
        params,
        Text("\n"),
        separator,
        Text("\n"),
        viewport,
        Text("\n"),
        separator,
        Text("\n"),
        status,
    )

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Use different colors based on exit code
    if data.exit_code == 0:
        border_color = UI_COLORS["success"]
        status_text = "done"
    else:
        border_color = UI_COLORS["warning"]
        status_text = f"exit {data.exit_code}"

    return Panel(
        content,
        title=f"[{border_color}]bash[/] [{status_text}]",
        subtitle=f"[{UI_COLORS['muted']}]{timestamp}[/]",
        border_style=Style(color=border_color),
        padding=(0, 1),
        expand=False,
    )
