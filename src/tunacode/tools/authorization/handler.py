from __future__ import annotations

from tunacode.templates.loader import Template
from tunacode.types import (
    StateManagerProtocol,
    ToolArgs,
    ToolConfirmationRequest,
    ToolConfirmationResponse,
    ToolName,
)

from .context import AuthContext
from .factory import create_default_authorization_policy
from .notifier import ToolRejectionNotifier
from .policy import AuthorizationPolicy
from .requests import ConfirmationRequestFactory
from .types import AuthorizationResult


class ToolHandler:
    """Coordinate tool authorization, confirmation, and rejection handling."""

    def __init__(
        self,
        state_manager: StateManagerProtocol,
        policy: AuthorizationPolicy | None = None,
        notifier: ToolRejectionNotifier | None = None,
        factory: ConfirmationRequestFactory | None = None,
    ):
        self.state = state_manager
        self.active_template: Template | None = None

        self._policy = policy or create_default_authorization_policy()
        self._notifier = notifier or ToolRejectionNotifier()
        self._factory = factory or ConfirmationRequestFactory()

        if state_manager.tool_handler is None:
            state_manager.set_tool_handler(self)

    def set_active_template(self, template: Template | None) -> None:
        self.active_template = template

    def get_authorization(self, tool_name: ToolName) -> AuthorizationResult:
        """Get authorization decision for a tool."""
        context = AuthContext.from_state(self.state)
        return self._policy.get_authorization(tool_name, context)

    def should_confirm(self, tool_name: ToolName) -> bool:
        """Legacy method - returns True if tool needs confirmation or is denied."""
        context = AuthContext.from_state(self.state)
        return self._policy.should_confirm(tool_name, context)

    def process_confirmation(self, response: ToolConfirmationResponse, tool_name: ToolName) -> bool:
        if response.skip_future:
            self.state.session.tool_ignore.append(tool_name)

        if not response.approved or response.abort:
            self._notifier.notify_rejection(tool_name, response, self.state)

        return response.approved and not response.abort

    def create_confirmation_request(
        self, tool_name: ToolName, args: ToolArgs
    ) -> ToolConfirmationRequest:
        return self._factory.create(tool_name, args)
