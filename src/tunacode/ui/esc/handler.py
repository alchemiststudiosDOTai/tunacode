"""ESC handler orchestration."""

from __future__ import annotations

from tunacode.ui.esc.types import EditorProtocol, RequestTask, ShellRunnerProtocol


class EscHandler:
    """Handle ESC key events using an explicit, dependency-injected flow."""

    def handle_escape(
        self,
        *,
        current_request_task: RequestTask | None,
        shell_runner: ShellRunnerProtocol | None,
        editor: EditorProtocol,
    ) -> None:
        request_task = current_request_task
        request_task_active = request_task is not None
        if request_task_active:
            assert request_task is not None
            request_task.cancel()
            return

        if shell_runner is not None and shell_runner.is_running():
            shell_runner.cancel()
            return

        editor_has_value = bool(editor.value)
        editor_has_paste_buffer = editor.has_paste_buffer
        editor_has_input = editor_has_value or editor_has_paste_buffer
        if editor_has_input:
            editor.clear_input()
