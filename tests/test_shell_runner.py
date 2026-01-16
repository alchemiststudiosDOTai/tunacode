"""Tests for ShellRunner negative boundary conditions."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field

import pytest
from rich.console import RenderableType

from tunacode.ui.shell_runner import (
    SHELL_COMMAND_USAGE_TEXT,
    ShellRunner,
    ShellRunnerHost,
)

DEFAULT_TOOL_PANEL_WIDTH: int = 80


@dataclass
class MockHost(ShellRunnerHost):
    """Captures ShellRunnerHost calls for test assertions."""

    tool_width: int = DEFAULT_TOOL_PANEL_WIDTH
    notifications: list[tuple[str, str]] = field(default_factory=list)
    outputs: list[RenderableType] = field(default_factory=list)
    status_running_count: int = 0
    status_last_count: int = 0

    def notify(self, message: str, severity: str = "information") -> None:
        self.notifications.append((message, severity))

    def write_shell_output(self, renderable: RenderableType) -> None:
        self.outputs.append(renderable)

    def shell_status_running(self) -> None:
        self.status_running_count += 1

    def shell_status_last(self) -> None:
        self.status_last_count += 1

    def tool_panel_max_width(self) -> int:
        return self.tool_width


class TestShellRunnerNegativeBoundaries:
    """Negative boundary tests for ShellRunner."""

    def test_empty_command_shows_usage(self) -> None:
        """start('') notifies usage text, doesn't start a task."""
        host = MockHost()
        runner = ShellRunner(host=host)

        runner.start("")

        assert runner.is_running() is False
        assert len(host.notifications) == 1
        assert host.notifications[0] == (SHELL_COMMAND_USAGE_TEXT, "warning")
        assert len(host.outputs) == 0

    def test_whitespace_only_command_shows_usage(self) -> None:
        """start('   ') treats whitespace-only as empty."""
        host = MockHost()
        runner = ShellRunner(host=host)

        runner.start("   \t\n  ")

        assert runner.is_running() is False
        assert len(host.notifications) == 1
        assert host.notifications[0] == (SHELL_COMMAND_USAGE_TEXT, "warning")

    @pytest.mark.asyncio
    async def test_already_running_blocks_second_start(self) -> None:
        """start() while running warns and doesn't start second task."""
        host = MockHost()
        runner = ShellRunner(host=host)

        # Start a long-running command
        runner.start("sleep 10")

        # Give task a moment to start
        await asyncio.sleep(0.01)

        assert runner.is_running() is True
        initial_notifications = len(host.notifications)

        # Try to start another command
        runner.start("echo hello")

        # Should warn, not start second task
        assert runner.is_running() is True
        assert len(host.notifications) == initial_notifications + 1
        assert "already running" in host.notifications[-1][0].lower()
        assert host.notifications[-1][1] == "warning"

        # Cleanup: cancel the running task and wait for completion
        runner.cancel()
        # Wait for the internal task to finish (it handles CancelledError internally)
        task = runner._task
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                await asyncio.wait_for(task, timeout=2.0)
