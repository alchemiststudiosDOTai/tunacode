"""Core-specific type exports."""

from __future__ import annotations

import importlib
from typing import Any

_TYPE_EXPORTS = {
    "AgentState": ".agent_state",
    "ResponseState": ".agent_state",
    "SessionStateProtocol": ".state",
    "StateManagerProtocol": ".state",
    "ConversationState": ".state_structures",
    "RuntimeState": ".state_structures",
    "TaskState": ".state_structures",
    "UsageState": ".state_structures",
}


def __getattr__(name: str) -> Any:
    module_name = _TYPE_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module_name, __name__), name)
