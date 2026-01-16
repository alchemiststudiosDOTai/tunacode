"""Async shell command runner for the Textual TUI."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Protocol

from rich.console import RenderableType
from rich.text import Text

from tunacode.constants import MAX_PANEL_LINE_WIDTH
from tunacode.ui.renderers.tools.bash import render_bash

SHELL_COMMAND_TIMEOUT_SECONDS: float = 30.0
SHELL_COMMAND_CANCEL_GRACE_SECONDS: float = 0.5
SHELL_COMMAND_USAGE_TEXT = "Usage: !<command>"
SHELL_OUTPUT_ENCODING = "utf-8"
SHELL_CANCEL_SIGNAL = signal.SIGINT

# Output placeholders for empty streams
SHELL_OUTPUT_EMPTY = "(no output)"
SHELL_STDERR_EMPTY = "(no errors)"

# Error handler defaults
SHELL_ERROR_CMD_PLACEHOLDER = "(shell error)"
SHELL_ERROR_EXIT_CODE = 1
SHELL_ERROR_DURATION_MS = 0.0

# Conversion factors
MS_PER_SECOND = 1000
DEFAULT_EXIT_CODE = 1


class ShellRunnerHost(Protocol):
    def notify(self, message: str, severity: str = "information") -> None: ...

    def write_shell_output(self, renderable: RenderableType) -> None: ...

    def shell_status_running(self) -> None: ...

    def shell_status_last(self) -> None: ...


@dataclass
class ShellRunner:
    host: ShellRunnerHost

    _task: asyncio.Task[None] | None = None
    _process: asyncio.subprocess.Process | None = None

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, raw_cmd: str) -> None:
        cmd = raw_cmd.strip()
        if not cmd:
            self.host.notify(SHELL_COMMAND_USAGE_TEXT, severity="warning")
            return

        if self.is_running():
            self.host.notify(
                "Shell command already running (! or Esc to cancel)",
                severity="warning",
            )
            return

        self._task = asyncio.create_task(self._run(cmd))
        self._task.add_done_callback(self._on_done)

    def cancel(self) -> None:
        if not self.is_running():
            return

        process = self._process
        if process is None:
            assert self._task is not None
            self._task.cancel()
            return

        try:
            process.send_signal(SHELL_CANCEL_SIGNAL)
        except ProcessLookupError:
            assert self._task is not None
            self._task.cancel()
            return

        assert self._task is not None
        self._task.cancel()

    def _format_shell_panel(
        self,
        cmd: str,
        exit_code: int,
        cwd: str,
        stdout: str,
        stderr: str,
        duration_ms: float,
    ) -> RenderableType:
        """Format shell output as 4-zone NeXTSTEP panel via BashRenderer."""
        stdout_text = stdout if stdout else SHELL_OUTPUT_EMPTY
        stderr_text = stderr if stderr else SHELL_STDERR_EMPTY

        result_text = f"""Command: {cmd}
Exit Code: {exit_code}
Working Directory: {cwd}

STDOUT:
{stdout_text}

STDERR:
{stderr_text}"""

        args = {"timeout": int(SHELL_COMMAND_TIMEOUT_SECONDS)}
        panel = render_bash(args, result_text, duration_ms, MAX_PANEL_LINE_WIDTH)

        if panel is None:
            return Text(f"$ {cmd}\n{stdout_text}\n{stderr_text}")
        return panel

    def _on_done(self, task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            # TODO(#225): preserve original command context instead of placeholder
            cwd = os.getcwd()
            panel = self._format_shell_panel(
                cmd=SHELL_ERROR_CMD_PLACEHOLDER,
                exit_code=SHELL_ERROR_EXIT_CODE,
                cwd=cwd,
                stdout="",
                stderr=str(exc),
                duration_ms=SHELL_ERROR_DURATION_MS,
            )
            self.host.write_shell_output(panel)

    async def _wait_or_kill_process(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return

        try:
            await asyncio.wait_for(process.wait(), timeout=SHELL_COMMAND_CANCEL_GRACE_SECONDS)
        except TimeoutError:
            process.kill()
            await process.wait()

    async def _run(self, cmd: str) -> None:
        self.host.shell_status_running()
        self.host.notify(f"Running: {cmd}")

        cwd = os.getcwd()
        start_time = time.perf_counter()

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        self._process = process

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=SHELL_COMMAND_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            self.host.notify("Command timed out", severity="error")
            return
        except asyncio.CancelledError:
            await self._wait_or_kill_process(process)
            self.host.notify("Shell command cancelled", severity="warning")
            raise
        finally:
            self._process = None
            self.host.shell_status_last()

        duration_ms = (time.perf_counter() - start_time) * MS_PER_SECOND
        exit_code = process.returncode if process.returncode is not None else DEFAULT_EXIT_CODE

        stdout = (stdout_bytes or b"").decode(SHELL_OUTPUT_ENCODING, errors="replace").rstrip()
        stderr = (stderr_bytes or b"").decode(SHELL_OUTPUT_ENCODING, errors="replace").rstrip()

        panel = self._format_shell_panel(cmd, exit_code, cwd, stdout, stderr, duration_ms)
        self.host.write_shell_output(panel)

        if exit_code != 0:
            self.host.notify(f"Exit code: {exit_code}", severity="warning")
