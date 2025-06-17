from __future__ import annotations

from typing import Any, Dict, List

from ..llm.planner import make_plan
from ..state import StateManager
from .planner_schema import Task
from ..tool_handler import ToolHandler
from ...types import ModelName


class ReActAgent:
    """Adaptive agent that plans and executes tasks step by step."""

    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.tool_handler = ToolHandler(state_manager)

    async def plan(self, request: str, model: ModelName) -> List[Task]:
        """Generate a list of tasks for the given request."""
        return await make_plan(request, model, self.state)

    async def _execute_task(self, task: Task) -> Dict[str, Any]:
        output = await self.tool_handler.execute(task)
        return {"task_id": task.id, "output": output}

    async def run(self, request: str, model: ModelName | None = None) -> List[Dict[str, Any]]:
        """Plan the request and execute each task sequentially."""
        model = model or self.state.session.current_model
        tasks = await self.plan(request, model)
        results: List[Dict[str, Any]] = []
        for task in tasks:
            results.append(await self._execute_task(task))
        return results
