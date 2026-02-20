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
            logger.info(debug_message)
            logger.info("Lifecycle logging enabled")
            log_usage_update(
                logger=logger,
                request_id=session.runtime.request_id,
                event_name="debug_toggle",
                last_call_usage=session.usage.last_call_usage,
                session_total_usage=session.usage.session_total_usage,
            )
