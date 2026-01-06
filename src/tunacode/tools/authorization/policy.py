from __future__ import annotations

from tunacode.types import ToolName

from .context import AuthContext
from .rules import AuthorizationRule
from .types import AuthorizationResult


class AuthorizationPolicy:
    """Evaluate authorization rules to decide if confirmation is required."""

    def __init__(self, rules: list[AuthorizationRule]):
        self._rules = sorted(rules, key=lambda rule: rule.priority())

    def get_authorization(self, tool_name: ToolName, context: AuthContext) -> AuthorizationResult:
        """Evaluate rules and return authorization decision.

        Checks for DENY first (via evaluate() method), then ALLOW, finally CONFIRM.
        """
        # First pass: check for DENY from rules with evaluate() method
        for rule in self._rules:
            if hasattr(rule, "evaluate"):
                result = rule.evaluate(tool_name, context)
                if result == AuthorizationResult.DENY:
                    return AuthorizationResult.DENY

        # Second pass: check for ALLOW via should_allow_without_confirmation
        for rule in self._rules:
            if rule.should_allow_without_confirmation(tool_name, context):
                return AuthorizationResult.ALLOW

        return AuthorizationResult.CONFIRM

    def should_confirm(self, tool_name: ToolName, context: AuthContext) -> bool:
        """Legacy method for backward compatibility."""
        result = self.get_authorization(tool_name, context)
        # DENY treated as "needs confirmation" for legacy callers
        # but will be handled specially in the new flow
        return result != AuthorizationResult.ALLOW
