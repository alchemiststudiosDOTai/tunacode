"""NeXTSTEP-style panel renderer for bash tool output.

Displays command output with smart code detection and syntax highlighting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text

from tunacode.constants import MIN_VIEWPORT_LINES

from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    RendererConfig,
    build_hook_params_prefix,
    tool_renderer,
    truncate_content,
    truncate_line,
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


class BashRenderer(BaseToolRenderer[BashData]):
    """Renderer for bash command output with exit code coloring."""

    def parse_result(self, args: dict[str, Any] | None, result: str) -> BashData | None:
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

    def build_header(
        self,
        data: BashData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 1: Command + exit status indicator."""
        header = Text()

        cmd_display = truncate_line(data.command, max_width=max_line_width)
        header.append(f"$ {cmd_display}", style="bold")

        if data.exit_code == 0:
            header.append("   ", style="")
            header.append("ok", style="green bold")
        else:
            header.append("   ", style="")
            header.append(f"exit {data.exit_code}", style="red bold")

        return header

    def build_params(self, data: BashData, max_line_width: int) -> Text | None:
        """Zone 2: Working directory and timeout."""
        params = build_hook_params_prefix()
        params.append("cwd:", style="dim")
        params.append(f" {data.working_dir}", style="dim bold")
        params.append("  timeout:", style="dim")
        params.append(f" {data.timeout}s", style="dim bold")
        return params

    def _detect_output_type(self, command: str, output: str) -> str | None:
        """Detect lexer from command or output content."""
        # Check command for hints
        cmd_lower = command.lower()

        # JSON output commands
        is_json_cmd = any(x in cmd_lower for x in ["--json", "-j ", "| jq", "curl ", "http"])
        if is_json_cmd and output.strip().startswith(("{", "[")):
            return "json"

        # Python commands
        if cmd_lower.startswith(("python", "uv run python", "pytest")):
            return None  # Usually plain output, not code

        # Git commands with special output
        if cmd_lower.startswith("git diff"):
            return "diff"
        if cmd_lower.startswith("git log") and "--format" not in cmd_lower:
            return None

        # Try content-based detection
        return detect_code_lexer(output)

    def build_viewport(self, data: BashData, max_line_width: int) -> RenderableType:
        """Zone 3: stdout/stderr output with smart highlighting."""
        viewport_parts: list[RenderableType] = []

        if data.stdout:
            truncated_stdout, _, _ = truncate_content(data.stdout, max_width=max_line_width)

            # Try to detect if output is code
            lexer = self._detect_output_type(data.command, data.stdout)

            stdout_header = Text()
            stdout_header.append("stdout", style="dim bold")
            if lexer:
                stdout_header.append(f" ({lexer})", style="dim italic")
            stdout_header.append(":", style="dim")
            viewport_parts.append(stdout_header)

            if lexer:
                viewport_parts.append(syntax_or_text(truncated_stdout, lexer=lexer))
            else:
                viewport_parts.append(Text(truncated_stdout))

        if data.stderr:
            if viewport_parts:
                viewport_parts.append(Text(""))

            stderr_header = Text()
            stderr_header.append("stderr:", style="dim bold red")
            viewport_parts.append(stderr_header)

            truncated_stderr, _, _ = truncate_content(data.stderr, max_width=max_line_width)
            stderr_text = Text(truncated_stderr, style="red")
            viewport_parts.append(stderr_text)

        if not viewport_parts:
            viewport_parts.append(Text("(no output)", style="dim italic"))

        # Pad viewport to minimum height
        viewport_line_count = 0
        for part in viewport_parts:
            if isinstance(part, Text):
                viewport_line_count += 1 + str(part).count("\n")
            else:
                viewport_line_count += 1

        while viewport_line_count < MIN_VIEWPORT_LINES:
            viewport_parts.append(Text(""))
            viewport_line_count += 1

        return Group(*viewport_parts)

    def build_status(
        self,
        data: BashData,
        duration_ms: float | None,
        max_line_width: int,
    ) -> Text:
        """Zone 4: Truncation info, line counts, duration."""
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

        return Text("  ".join(status_items), style="dim") if status_items else Text("")

    def get_border_color(self, data: BashData) -> str:
        """Green for success, warning for non-zero exit."""
        if data.exit_code == 0:
            return self.config.success_color
        return self.config.warning_color

    def get_status_text(self, data: BashData) -> str:
        """'done' for success, 'exit N' for failure."""
        if data.exit_code == 0:
            return "done"
        return f"exit {data.exit_code}"


_renderer = BashRenderer(RendererConfig(tool_name="bash"))


@tool_renderer("bash")
def render_bash(
    args: dict[str, Any] | None,
    result: str,
    duration_ms: float | None,
    max_line_width: int,
) -> RenderableType | None:
    """Render bash with NeXTSTEP zoned layout."""
    return _renderer.render(args, result, duration_ms, max_line_width)
