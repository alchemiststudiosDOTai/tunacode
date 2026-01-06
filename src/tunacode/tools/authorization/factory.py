from __future__ import annotations

from .policy import AuthorizationPolicy
from .rules import (
    AuthorizationRule,
    PlanModeBlockRule,
    ReadOnlyToolRule,
    TemplateAllowedToolsRule,
    ToolIgnoreListRule,
    YoloModeRule,
)


def create_default_authorization_policy() -> AuthorizationPolicy:
    rules: list[AuthorizationRule] = [
        PlanModeBlockRule(),  # Priority 100 - checked first, can DENY
        ReadOnlyToolRule(),
        TemplateAllowedToolsRule(),
        YoloModeRule(),
        ToolIgnoreListRule(),
    ]
    return AuthorizationPolicy(rules)
