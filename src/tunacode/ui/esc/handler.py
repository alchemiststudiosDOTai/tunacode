"""ESC handler orchestration."""

from __future__ import annotations

from tunacode.ui.esc.types import RequestTask, ShellRunnerProtocol


class EscHandler:
    """Handle ESC key events using an explicit, dependency-injected flow."""

    def handle_escape(
        self,
        *,
        current_request_task: RequestTask | None,
        shell_runner: ShellRunnerProtocol | None,
    ) -> None:
        if current_request_task is not None:
            current_request_task.cancel()
            return

        if shell_runner is not None and shell_runner.is_running():
            shell_runner.cancel()
            return
