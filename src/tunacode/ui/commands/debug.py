"""Debug command for toggling UI debug logging."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


class DebugCommand(Command):
    """Toggle debug logging to the screen and configured file logger."""

    name = "debug"
    description = "Toggle debug logging to screen"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from tunacode.core.debug import log_usage_update
        from tunacode.core.logging import get_logger

        from tunacode.ui.request_debug import build_request_debug_thresholds_message

        session = app.state_manager.session
        session.debug_mode = not session.debug_mode

        logger = get_logger()
        logger.set_debug_mode(session.debug_mode)
        log_path = logger.log_path

        status = "ON" if session.debug_mode else "OFF"
        app.notify(f"Debug mode: {status}")

        if session.debug_mode:
            log_path_display = str(log_path)
            debug_message = f"Debug logging enabled. Log file: {log_path_display}"
            app.chat_container.write(
                f"[dim]Debug logging enabled. Logs also written to {log_path_display}[/dim]"
            )
            app.chat_container.write(
                "[dim]Parallel tool-call traces appear as lifecycle lines "
                "prefixed with 'Parallel tool calls'.[/dim]"
            )
            app.chat_container.write(
                "[dim]Input/request latency traces use lifecycle prefixes "
                "'Input:', 'Queue:', 'Bridge:', 'UI:', and 'Init:'.[/dim]"
            )
            app.chat_container.write(
                "[dim]Tail latency now breaks out final_flush, response_panel, "
                "resource_bar, and save_session timings.[/dim]"
            )
            logger.info(debug_message)
            logger.info("Lifecycle logging enabled")
            logger.lifecycle(build_request_debug_thresholds_message())
            log_usage_update(
                logger=logger,
                request_id=session.runtime.request_id,
                event_name="debug_toggle",
                last_call_usage=session.usage.last_call_usage,
                session_total_usage=session.usage.session_total_usage,
            )
