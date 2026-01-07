"""Lightweight ReAct-style scratchpad tool."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic_ai.exceptions import ModelRetry

from tunacode.types import StateManagerProtocol


def create_react_tool(state_manager: StateManagerProtocol) -> Callable:
    """Factory to create a react tool bound to a state manager.

    Args:
        state_manager: The state manager instance to use.

    Returns:
        An async function that implements the react tool.
    """

    async def react(
        action: Literal["think", "observe", "get", "clear"],
        thoughts: str | None = None,
        next_action: str | None = None,
        result: str | None = None,
    ) -> str:
        """ReAct scratchpad for tracking think/observe steps.

        Args:
            action: The action to perform (think/observe/get/clear).
            thoughts: Thought content for think action.
            next_action: Planned next action for think action.
            result: Observation message for observe action.

        Returns:
            Status message or scratchpad contents.
        """
        scratchpad = state_manager.get_react_scratchpad()
        scratchpad.setdefault("timeline", [])

        if action == "think":
            if not thoughts:
                raise ModelRetry("Provide thoughts when using react think action")
            if not next_action:
                raise ModelRetry("Specify next_action when recording react thoughts")

            entry = {"type": "think", "thoughts": thoughts, "next_action": next_action}
            state_manager.append_react_entry(entry)
            return "Recorded think step"

        if action == "observe":
            if not result:
                raise ModelRetry("Provide result when using react observe action")

            entry = {"type": "observe", "result": result}
            state_manager.append_react_entry(entry)
            return "Recorded observation"

        if action == "get":
            timeline = scratchpad.get("timeline", [])
            if not timeline:
                return "React scratchpad is empty"

            formatted = [
                f"{i + 1}. {item['type']}: {_format_entry(item)}" for i, item in enumerate(timeline)
            ]
            return "\n".join(formatted)

        if action == "clear":
            state_manager.clear_react_scratchpad()
            return "React scratchpad cleared"

        raise ModelRetry("Invalid react action. Use one of: think, observe, get, clear")

    return react


def _format_entry(item: dict[str, Any]) -> str:
    """Format a scratchpad entry for display."""
    if item["type"] == "think":
        return f"thoughts='{item['thoughts']}', next_action='{item['next_action']}'"
    if item["type"] == "observe":
        return f"result='{item['result']}'"
    return str(item)


# Backwards compatibility: ReactTool class wrapper
class ReactTool:
    """Wrapper class for backwards compatibility with existing code."""

    def __init__(self, state_manager: StateManagerProtocol) -> None:
        self.state_manager = state_manager
        self._react = create_react_tool(state_manager)

    @property
    def tool_name(self) -> str:
        return "react"

    async def execute(
        self,
        action: Literal["think", "observe", "get", "clear"],
        thoughts: str | None = None,
        next_action: str | None = None,
        result: str | None = None,
    ) -> str:
        """Execute the react tool."""
        return await self._react(
            action=action, thoughts=thoughts, next_action=next_action, result=result
        )
