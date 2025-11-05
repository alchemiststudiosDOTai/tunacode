"""
Tool handling business logic, separated from UI concerns.

Refactored to use composition with specialized authorization components:
- AuthorizationPolicy: Determines if tools require confirmation
- ToolRejectionNotifier: Handles agent communication on rejection
- ConfirmationRequestFactory: Creates confirmation requests for UI

This eliminates the "God Object" anti-pattern by delegating to focused components.
"""

from typing import Optional

from tunacode.core.state import StateManager
from tunacode.core.tool_authorization import (
    AuthContext,
    AuthorizationPolicy,
    ConfirmationRequestFactory,
    ToolRejectionNotifier,
    create_default_authorization_policy,
)
from tunacode.templates.loader import Template
from tunacode.types import (
    ToolArgs,
    ToolConfirmationRequest,
    ToolConfirmationResponse,
    ToolName,
)


class ToolHandler:
    """Coordinates tool authorization, confirmation, and rejection handling.

    Refactored to use Facade pattern, delegating to specialized components:
    - AuthorizationPolicy: Determines if confirmation is needed
    - ToolRejectionNotifier: Handles agent communication
    - ConfirmationRequestFactory: Creates confirmation requests

    This eliminates the "God Object" anti-pattern by separating concerns.
    """

    def __init__(
        self,
        state_manager: StateManager,
        policy: Optional[AuthorizationPolicy] = None,
        notifier: Optional[ToolRejectionNotifier] = None,
        factory: Optional[ConfirmationRequestFactory] = None,
    ):
        """Initialize tool handler with injected dependencies.

        Dependencies are optional to maintain backward compatibility during
        refactoring. Defaults are provided for gradual migration.

        Args:
            state_manager: State manager for session state access
            policy: Authorization policy (default: create standard policy)
            notifier: Rejection notifier (default: create standard notifier)
            factory: Confirmation factory (default: create standard factory)
        """
        self.state = state_manager
        self.active_template: Optional[Template] = None  # Kept for compatibility

        # Inject dependencies with defaults
        self._policy = policy or create_default_authorization_policy()
        self._notifier = notifier or ToolRejectionNotifier()
        self._factory = factory or ConfirmationRequestFactory()

        # Register self with state manager if not already set
        # This ensures AuthContext can read active_template
        if state_manager.tool_handler is None:
            state_manager.set_tool_handler(self)

    def set_active_template(self, template: Optional[Template]) -> None:
        """Set the currently active template.

        Args:
            template: The template to activate, or None to clear the active template.
        """
        self.active_template = template

    def should_confirm(self, tool_name: ToolName) -> bool:
        """Determine if a tool requires confirmation.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if confirmation is required, False otherwise.
        """
        context = AuthContext.from_state(self.state)
        return self._policy.should_confirm(tool_name, context)

    def is_tool_blocked_in_plan_mode(self, tool_name: ToolName) -> bool:
        """Check if tool is blocked in plan mode.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if tool is blocked in plan mode, False otherwise.
        """
        context = AuthContext.from_state(self.state)
        return self._policy.is_tool_blocked(tool_name, context)

    def process_confirmation(self, response: ToolConfirmationResponse, tool_name: ToolName) -> bool:
        """Process the confirmation response.

        Handles skip_future preference and rejection notification.

        Args:
            response: The confirmation response from the user.
            tool_name: Name of the tool being confirmed.

        Returns:
            True if tool should proceed, False if aborted.
        """
        if response.skip_future:
            self.state.session.tool_ignore.append(tool_name)

        if not response.approved or response.abort:
            self._notifier.notify_rejection(tool_name, response, self.state)

        return response.approved and not response.abort

    def create_confirmation_request(
        self, tool_name: ToolName, args: ToolArgs
    ) -> ToolConfirmationRequest:
        """Create a confirmation request from tool information.

        Args:
            tool_name: Name of the tool.
            args: Tool arguments.

        Returns:
            Structured confirmation request for UI.
        """
        return self._factory.create(tool_name, args)
