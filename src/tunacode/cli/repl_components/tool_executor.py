"""
Module: tunacode.cli.repl_components.tool_executor

Tool execution and confirmation handling for the REPL.
"""

import logging
from asyncio.exceptions import CancelledError

from prompt_toolkit.application import run_in_terminal

from tunacode.core.agents import patch_tool_messages
from tunacode.core.tool_handler import ToolHandler
from tunacode.exceptions import UserAbortError
from tunacode.types import StateManager
from tunacode.ui import console as ui
from tunacode.ui.tool_ui import ToolUI

from .command_parser import parse_args

logger = logging.getLogger(__name__)

_tool_ui = ToolUI()

MSG_OPERATION_ABORTED_BY_USER = "Operation aborted by user."


async def tool_handler(part, state_manager: StateManager):
    """Handle tool execution with separated business logic and UI."""
    # Check for cancellation before tool execution (only if explicitly set to True)
    operation_cancelled = getattr(state_manager.session, "operation_cancelled", False)
    if operation_cancelled is True:
        logger.debug("Tool execution cancelled")
        raise CancelledError("Operation was cancelled")

    # Get or create tool handler
    if state_manager.tool_handler is None:
        tool_handler_instance = ToolHandler(state_manager)
        state_manager.set_tool_handler(tool_handler_instance)
    else:
        tool_handler_instance = state_manager.tool_handler

    if tool_handler_instance.should_confirm(part.tool_name):
        await ui.info(f"Tool({part.tool_name})")

    # Keep spinner running during tool execution - it will be updated with tool status
    # if not state_manager.session.is_streaming_active and state_manager.session.spinner:
    #     state_manager.session.spinner.stop()

    streaming_panel = None
    if state_manager.session.is_streaming_active and hasattr(
        state_manager.session, "streaming_panel"
    ):
        streaming_panel = state_manager.session.streaming_panel
        if streaming_panel and tool_handler_instance.should_confirm(part.tool_name):
            await streaming_panel.stop()

    try:
        args = parse_args(part.args)

        def confirm_func():
            # Check if tool is blocked in plan mode first
            if tool_handler_instance.is_tool_blocked_in_plan_mode(part.tool_name):
                from tunacode.constants import READ_ONLY_TOOLS

                error_msg = (
                    f"🔍 Plan Mode: Tool '{part.tool_name}' is not available in Plan Mode.\n"
                    f"Only read-only tools are allowed: {', '.join(READ_ONLY_TOOLS)}\n"
                    f"Use 'exit_plan_mode' tool to present your plan and exit Plan Mode."
                )
                print(f"\n❌ {error_msg}\n")
                return True  # Abort the tool

            if not tool_handler_instance.should_confirm(part.tool_name):
                return False
            request = tool_handler_instance.create_confirmation_request(part.tool_name, args)

            response = _tool_ui.show_sync_confirmation(request)

            if not tool_handler_instance.process_confirmation(response, part.tool_name):
                return True  # Abort
            return False  # Continue

        should_abort = await run_in_terminal(confirm_func)

        if should_abort:
            raise UserAbortError("User aborted.")

    except UserAbortError:
        patch_tool_messages(MSG_OPERATION_ABORTED_BY_USER, state_manager)
        raise
    finally:
        if streaming_panel and tool_handler_instance.should_confirm(part.tool_name):
            await streaming_panel.start()

        # Spinner continues running - no need to restart
        # if not state_manager.session.is_streaming_active and state_manager.session.spinner:
        #     state_manager.session.spinner.start()
