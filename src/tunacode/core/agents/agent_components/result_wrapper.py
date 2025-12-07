"""Result wrapper classes for agent responses."""

from typing import Any


class SimpleResult:
    """Simple result wrapper for fallback responses."""

    def __init__(self, output: str):
        self.output = output


class AgentRunWrapper:
    """Wrapper that adds response_state to agent run results."""

    def __init__(self, wrapped_run: Any, fallback_result: Any, response_state: Any = None):
        self._wrapped = wrapped_run
        self._result = fallback_result
        self.response_state = response_state

    def __getattribute__(self, name: str) -> Any:
        # Handle special attributes first to avoid conflicts
        if name in ["_wrapped", "_result", "response_state"]:
            return object.__getattribute__(self, name)

        # Explicitly handle 'result' to return our fallback result
        if name == "result":
            return object.__getattribute__(self, "_result")

        # Delegate all other attributes to the wrapped object
        try:
            return getattr(object.__getattribute__(self, "_wrapped"), name)
        except AttributeError:
            msg = f"'{type(self).__name__}' object has no attribute '{name}'"
            raise AttributeError(msg) from None


class AgentRunWithState:
    """Minimal wrapper to add response_state to agent runs."""

    def __init__(self, wrapped_run: Any, response_state: Any = None):
        self._wrapped = wrapped_run
        self.response_state = response_state

    def __getattribute__(self, name: str) -> Any:
        # Handle special attributes first
        if name in ["_wrapped", "response_state"]:
            return object.__getattribute__(self, name)

        # Delegate all other attributes to the wrapped object
        return getattr(object.__getattribute__(self, "_wrapped"), name)
