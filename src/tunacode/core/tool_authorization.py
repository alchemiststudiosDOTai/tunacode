"""
Tool authorization system with separated concerns.

This module implements a declarative, rule-based authorization system for
tool execution confirmation. It replaces the complex nested conditionals in
the original ToolHandler with composable, testable authorization rules.

Architecture:
- AuthorizationRule (Protocol): Interface for authorization rules
- AuthContext: Immutable context for authorization decisions
- Concrete Rules: Specific authorization rules (ReadOnly, Template, YOLO, etc.)
- AuthorizationPolicy: Orchestrates multiple rules in priority order
- ToolRejectionNotifier: Handles agent communication on rejection
- ConfirmationRequestFactory: Creates confirmation requests for UI

Design Principles:
- Single Responsibility: Each class has one focused purpose
- Open/Closed: New rules can be added without modifying existing code
- Dependency Injection: Clear dependencies through constructors
- Testability: Each component can be tested in isolation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Protocol

from tunacode.constants import READ_ONLY_TOOLS, ToolName
from tunacode.types import ToolArgs, ToolConfirmationRequest, ToolConfirmationResponse

if TYPE_CHECKING:
    from tunacode.core.state import StateManager
    from tunacode.templates.loader import Template


# =============================================================================
# Authorization Context
# =============================================================================


@dataclass(frozen=True)
class AuthContext:
    """Immutable context for authorization decisions.

    Replaces mutable state access with explicit, immutable context. Makes all
    authorization inputs visible and testable.

    Attributes:
        yolo_mode: Whether YOLO mode is active (skip all confirmations)
        tool_ignore_list: Tools user has chosen to skip confirmation for
        active_template: Currently active template with allowed tools
    """

    yolo_mode: bool
    tool_ignore_list: tuple[ToolName, ...]  # Immutable tuple
    active_template: Optional[Template]

    @classmethod
    def from_state(cls, state: StateManager) -> AuthContext:
        """Create authorization context from current state.

        Args:
            state: State manager with current session state

        Returns:
            Immutable authorization context
        """
        # Get active_template from tool_handler if it exists
        active_template = None
        if hasattr(state, "tool_handler") and state.tool_handler is not None:
            active_template = getattr(state.tool_handler, "active_template", None)

        return cls(
            yolo_mode=state.session.yolo,
            tool_ignore_list=tuple(state.session.tool_ignore),
            active_template=active_template,
        )


# =============================================================================
# Authorization Rule Protocol
# =============================================================================


class AuthorizationRule(Protocol):
    """Protocol for authorization rules.

    Each rule encapsulates a single authorization concern. Rules are evaluated
    in priority order by AuthorizationPolicy.

    Priority Ranges:
        200-299: Allowlist rules (read-only, templates)
        300-399: User preference rules (YOLO, ignore list)
    """

    def should_allow_without_confirmation(self, tool_name: ToolName, context: AuthContext) -> bool:
        """Check if this rule allows the tool without confirmation.

        Args:
            tool_name: Tool being authorized
            context: Current authorization context

        Returns:
            True if this rule permits tool without confirmation
        """
        ...

    def priority(self) -> int:
        """Return priority for rule evaluation.

        Returns:
            Priority (lower number = higher priority)
        """
        ...


# =============================================================================
# Concrete Authorization Rules
# =============================================================================


class ReadOnlyToolRule:
    """Read-only tools are always safe to execute.

    Read-only tools (read_file, grep, list_dir, etc.) don't modify state,
    so they never require confirmation.

    Priority: 200 (allowlist rule)
    """

    def priority(self) -> int:
        return 200

    def should_allow_without_confirmation(self, tool_name: ToolName, context: AuthContext) -> bool:
        return is_read_only_tool(tool_name)


class TemplateAllowedToolsRule:
    """Tools allowed by active template don't require confirmation.

    Templates can pre-approve specific tools for workflow-specific operations.
    If a tool is in the active template's allowed_tools list, it can execute
    without confirmation.

    Priority: 210 (allowlist rule, after read-only)
    """

    def priority(self) -> int:
        return 210

    def should_allow_without_confirmation(self, tool_name: ToolName, context: AuthContext) -> bool:
        if context.active_template is None:
            return False

        if context.active_template.allowed_tools is None:
            return False

        return tool_name in context.active_template.allowed_tools


class YoloModeRule:
    """YOLO mode bypasses all confirmations.

    When YOLO mode is active, all tools can execute without confirmation.
    This is useful for batch operations or when the user trusts the agent.

    Priority: 300 (user preference rule)
    """

    def priority(self) -> int:
        return 300

    def should_allow_without_confirmation(self, tool_name: ToolName, context: AuthContext) -> bool:
        return context.yolo_mode


class ToolIgnoreListRule:
    """User-configured ignore list bypasses confirmations.

    Users can choose to skip confirmation for specific tools by adding them
    to the ignore list (via "skip future" in confirmation dialog).

    Priority: 310 (user preference rule, after YOLO)
    """

    def priority(self) -> int:
        return 310

    def should_allow_without_confirmation(self, tool_name: ToolName, context: AuthContext) -> bool:
        return tool_name in context.tool_ignore_list


# =============================================================================
# Authorization Policy
# =============================================================================


class AuthorizationPolicy:
    """Orchestrates authorization rules to determine if tools require confirmation.

    Uses Strategy pattern to compose multiple authorization rules.
    Evaluates allowlist rules in priority order.

    This replaces the complex nested conditionals in the original ToolHandler
    with a declarative, testable approach.
    """

    def __init__(self, rules: list[AuthorizationRule]):
        """Initialize with authorization rules.

        Args:
            rules: List of authorization rules to evaluate
        """
        # Sort rules by priority (lower number = higher priority)
        self._rules = sorted(rules, key=lambda r: r.priority())

    def should_confirm(self, tool_name: ToolName, context: AuthContext) -> bool:
        """Determine if tool requires user confirmation.

        Evaluates allowlist rules in priority order.

        Args:
            tool_name: Tool to authorize
            context: Current authorization context

        Returns:
            True if confirmation required, False otherwise
        """
        # Evaluate allowlist rules in priority order
        for rule in self._rules:
            if rule.should_allow_without_confirmation(tool_name, context):
                return False  # Rule allows tool without confirmation

        # No rule allowed it, require confirmation
        return True

    def is_tool_blocked(self, tool_name: ToolName, context: AuthContext) -> bool:
        """Check if tool is blocked.

        Returns:
            Always False (no tools are blocked)
        """
        return False


# =============================================================================
# Tool Rejection Notifier
# =============================================================================


class ToolRejectionNotifier:
    """Handles communication with agents when tools are rejected.

    Separates agent communication concerns from authorization logic. This
    eliminates the hidden dependency on the agent messaging system in the
    original ToolHandler.
    """

    def notify_rejection(
        self,
        tool_name: ToolName,
        response: ToolConfirmationResponse,
        state: StateManager,
    ) -> None:
        """Notify agent that tool execution was rejected.

        Routes user guidance back to agent system to maintain conversation
        context and enable the agent to respond appropriately.

        Args:
            tool_name: Tool that was rejected
            response: User's confirmation response with optional guidance
            state: State manager for routing message to agent
        """
        from tunacode.core.agents.agent_components.agent_helpers import create_user_message

        guidance = getattr(response, "instructions", "").strip()

        if guidance:
            guidance_section = f"User guidance:\n{guidance}"
        else:
            guidance_section = "User cancelled without additional instructions."

        message = (
            f"Tool '{tool_name}' execution cancelled before running.\n"
            f"{guidance_section}\n"
            "Do not assume the operation succeeded; "
            "request updated guidance or offer alternatives."
        )

        create_user_message(message, state)


# =============================================================================
# Confirmation Request Factory
# =============================================================================


class ConfirmationRequestFactory:
    """Creates confirmation requests from tool information.

    Separates UI concern (confirmation dialog creation) from business logic.
    Makes confirmation request creation testable in isolation.
    """

    def create(self, tool_name: ToolName, args: ToolArgs) -> ToolConfirmationRequest:
        """Create a confirmation request from tool information.

        Extracts relevant context (like filepath) for display in confirmation
        dialog.

        Args:
            tool_name: Name of tool requiring confirmation
            args: Tool arguments (may contain filepath, command, etc.)

        Returns:
            Structured confirmation request for UI
        """
        filepath = args.get("filepath")
        return ToolConfirmationRequest(tool_name=tool_name, args=args, filepath=filepath)


# =============================================================================
# Helper Functions
# =============================================================================


def is_read_only_tool(tool_name: str) -> bool:
    """Check if a tool is read-only (safe to execute without confirmation).

    Args:
        tool_name: Name of the tool to check

    Returns:
        True if the tool is read-only, False otherwise
    """
    return tool_name in READ_ONLY_TOOLS


def create_default_authorization_policy() -> AuthorizationPolicy:
    """Create default authorization policy with all standard rules.

    Returns:
        Authorization policy with standard rules in correct priority order
    """
    rules: list[AuthorizationRule] = [
        ReadOnlyToolRule(),
        TemplateAllowedToolsRule(),
        YoloModeRule(),
        ToolIgnoreListRule(),
    ]
    return AuthorizationPolicy(rules)
