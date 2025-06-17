from __future__ import annotations

from typing import Any, Dict, Callable

from .agents.planner_schema import Task
from ..tools.read_file import read_file
from ..tools.grep import grep
from ..tools.write_file import write_file
from ..tools.update_file import update_file
from ..tools.run_command import run_command
from ..tools.bash import bash
from ..tools.list_dir import list_dir


class ToolHandler:
    """Dispatch tasks to the appropriate tool functions."""

    def __init__(self, state_manager: Any):
        self.state = state_manager
        self._tools: Dict[str, Callable[..., Any]] = {
            "read_file": read_file,
            "grep": grep,
            "write_file": write_file,
            "update_file": update_file,
            "run_command": run_command,
            "bash": bash,
            "list_dir": list_dir,
        }

    async def execute(self, task: Task) -> Any:
        tool_name = task.tool
        func = self._tools.get(tool_name)
        if not func:
            raise ValueError(f"Unknown tool: {tool_name}")
        return await func(**task.args)
