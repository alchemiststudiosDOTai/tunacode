"""Continue command implementation for resuming interrupted operations."""

from typing import List

from tunacode.types import CommandContext
from tunacode.ui import console as ui
from ..base import CommandCategory, CommandSpec, SimpleCommand


class ContinueCommand(SimpleCommand):
    """Command to continue/resume an interrupted operation."""

    spec = CommandSpec(
        name="continue",
        aliases=["resume", "/continue", "/resume"],
        description="Continue the last interrupted operation",
        category=CommandCategory.DEVELOPMENT,
    )

    async def execute(self, args: List[str], context: CommandContext) -> None:
        """Execute the continue command."""
        state_manager = context.state_manager

        # Check if there's a pending request from when agent was busy
        if hasattr(state_manager.session, 'pending_request') and state_manager.session.pending_request:
            # Get the last pending request
            request = state_manager.session.pending_request.pop()
            await ui.info(f"Resuming request: {request[:50]}...")
            
            # Process the pending request
            if context.process_request:
                await context.process_request(request, state_manager)
            else:
                await ui.error("Cannot process request - processor not available")
            return

        # Check if there's a cancelled request to retry
        if hasattr(state_manager.session, 'last_cancelled_request'):
            request = state_manager.session.last_cancelled_request
            await ui.info(f"Retrying cancelled request: {request[:50]}...")
            
            # Clear the cancelled request
            delattr(state_manager.session, 'last_cancelled_request')
            
            # Process the request again
            if context.process_request:
                await context.process_request(request, state_manager)
            else:
                await ui.error("Cannot process request - processor not available")
            return

        await ui.muted("No interrupted operation to continue. Enter a new request.")