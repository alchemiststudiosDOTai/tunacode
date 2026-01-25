"""Lightweight ReAct-style scratchpad tool."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic_ai.exceptions import ModelRetry

from tunacode.types import StateManagerProtocol
from tunacode.types.canonical import ReActEntryKind


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

        if action == "think":
            if not thoughts:
                raise ModelRetry("Provide thoughts when using react think action")
            if not next_action:
                raise ModelRetry("Specify next_action when recording react thoughts")

            content = f"{thoughts} -> {next_action}"
            state_manager.append_react_entry(ReActEntryKind.THINK, content)
            return "Recorded think step"

        if action == "observe":
            if not result:
                raise ModelRetry("Provide result when using react observe action")

            state_manager.append_react_entry(ReActEntryKind.OBSERVE, result)
            return "Recorded observation"

        if action == "get":
            timeline = scratchpad.timeline
            if not timeline:
                return "React scratchpad is empty"

            formatted = [
                f"{i + 1}. {entry.kind.value}: {entry.content}" for i, entry in enumerate(timeline)
            ]
            return "\n".join(formatted)

        if action == "clear":
            state_manager.clear_react_scratchpad()
            return "React scratchpad cleared"

        raise ModelRetry("Invalid react action. Use one of: think, observe, get, clear")

    return react


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
