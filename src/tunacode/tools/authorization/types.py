"""Authorization types for tool access control."""

from __future__ import annotations

from enum import Enum


class AuthorizationResult(Enum):
    """Result of an authorization rule evaluation.

    ALLOW: Tool execution proceeds without confirmation
    CONFIRM: Tool requires user confirmation before execution
    DENY: Tool is blocked entirely (plan mode restriction)
    """

    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"
