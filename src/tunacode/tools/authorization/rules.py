from __future__ import annotations

from typing import Protocol

from tunacode.constants import EXECUTE_TOOLS, READ_ONLY_TOOLS, WRITE_TOOLS
from tunacode.types import ToolName

from .context import AuthContext
from .types import AuthorizationResult

READ_ONLY_TOOL_NAMES: set[str] = {tool.value for tool in READ_ONLY_TOOLS}
PLAN_MODE_BLOCKED_TOOLS: set[str] = {tool.value for tool in WRITE_TOOLS + EXECUTE_TOOLS}


class AuthorizationRule(Protocol):
    """Protocol for authorization rules."""

    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool: ...

    def priority(self) -> int: ...


class ReadOnlyToolRule:
    """Read-only tools are always safe to execute."""

    def priority(self) -> int:
        return 200

    def should_allow_without_confirmation(self, tool_name: ToolName, _: AuthContext) -> bool:
        return is_read_only_tool(tool_name)


class TemplateAllowedToolsRule:
    """Tools approved by the active template skip confirmation."""

    def priority(self) -> int:
        return 210

    def should_allow_without_confirmation(self, tool_name: ToolName, context: AuthContext) -> bool:
        if context.active_template is None:
            return False

        allowed_tools = context.active_template.allowed_tools
        if allowed_tools is None:
            return False

        return tool_name in allowed_tools


class YoloModeRule:
    """YOLO mode bypasses confirmations entirely."""

    def priority(self) -> int:
        return 300

    def should_allow_without_confirmation(self, _tool_name: ToolName, context: AuthContext) -> bool:
        return context.yolo_mode


class ToolIgnoreListRule:
    """User ignore list bypasses confirmation for selected tools."""

    def priority(self) -> int:
        return 310

    def should_allow_without_confirmation(self, tool_name: ToolName, context: AuthContext) -> bool:
        return tool_name in context.tool_ignore_list


class PlanModeBlockRule:
    """Block write/execute tools in plan mode. Highest priority - checked first."""

    def priority(self) -> int:
        return 100

    def evaluate(self, tool_name: ToolName, context: AuthContext) -> AuthorizationResult:
        """Return DENY for blocked tools in plan mode, CONFIRM otherwise."""
        if context.plan_mode and tool_name in PLAN_MODE_BLOCKED_TOOLS:
            return AuthorizationResult.DENY
        return AuthorizationResult.CONFIRM

    def should_allow_without_confirmation(self, tool_name: ToolName, context: AuthContext) -> bool:
        # This rule never allows - it only blocks or defers
        return False


def is_read_only_tool(tool_name: str) -> bool:
    """Check if the tool is classified as read-only."""
    return tool_name in READ_ONLY_TOOL_NAMES
