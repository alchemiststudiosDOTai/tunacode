"""Agent orchestration scaffolding.

This module defines an ``OrchestratorAgent`` class that demonstrates how
higher level planning and delegation could be layered on top of the existing
``process_request`` workflow.  The goal is to keep orchestration logic isolated
from the core agent implementation while reusing all current tooling and state
handling provided by ``main.process_request``.
"""

from __future__ import annotations

from typing import Any, List

from ...types import ModelName
from ..state import StateManager
from .react_agent import ReActAgent


class OrchestratorAgent:
    """Plan and run a sequence of sub-agent tasks."""

    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.react_agent = ReActAgent(state_manager)

    async def plan(self, request: str, model: ModelName) -> List[Any]:
        """Delegate planning to the underlying ReActAgent."""
        return await self.react_agent.plan(request, model)

    async def run(self, request: str, model: ModelName | None = None) -> List[Any]:
        """Run the request through the ReAct agent."""
        model = model or self.state.session.current_model
        return await self.react_agent.run(request, model)
