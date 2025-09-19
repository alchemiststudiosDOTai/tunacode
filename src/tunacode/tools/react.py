"""Lightweight ReAct-style scratchpad tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal

import defusedxml.ElementTree as ET
from pydantic_ai.exceptions import ModelRetry

from tunacode.core.state import StateManager
from tunacode.types import ToolResult, UILogger

from .base import BaseTool


# CLAUDE_ANCHOR[react-tool]: Minimal ReAct scratchpad tool surface
class ReactTool(BaseTool):
    """Minimal ReAct scratchpad for tracking think/observe steps."""

    def __init__(self, state_manager: StateManager, ui_logger: UILogger | None = None):
        super().__init__(ui_logger)
        self.state_manager = state_manager

    @property
    def tool_name(self) -> str:
        return "react"

    async def _execute(
        self,
        action: Literal["think", "observe", "get", "clear"],
        thoughts: str | None = None,
        next_action: str | None = None,
        result: str | None = None,
    ) -> ToolResult:
        scratchpad = self._ensure_scratchpad()

        if action == "think":
            if not thoughts:
                raise ModelRetry("Provide thoughts when using react think action")
            if not next_action:
                raise ModelRetry("Specify next_action when recording react thoughts")

            entry = {
                "type": "think",
                "thoughts": thoughts,
                "next_action": next_action,
            }
            self.state_manager.append_react_entry(entry)
            return "Recorded think step"

        if action == "observe":
            if not result:
                raise ModelRetry("Provide result when using react observe action")

            entry = {
                "type": "observe",
                "result": result,
            }
            self.state_manager.append_react_entry(entry)
            return "Recorded observation"

        if action == "get":
            timeline = scratchpad.get("timeline", [])
            if not timeline:
                return "React scratchpad is empty"

            formatted = [
                f"{index + 1}. {item['type']}: {self._format_entry(item)}"
                for index, item in enumerate(timeline)
            ]
            return "\n".join(formatted)

        if action == "clear":
            self.state_manager.clear_react_scratchpad()
            return "React scratchpad cleared"

        raise ModelRetry("Invalid react action. Use one of: think, observe, get, clear")

    def _format_entry(self, item: Dict[str, Any]) -> str:
        if item["type"] == "think":
            return f"thoughts='{item['thoughts']}', next_action='{item['next_action']}'"
        if item["type"] == "observe":
            return f"result='{item['result']}'"
        return str(item)

    def _ensure_scratchpad(self) -> dict[str, Any]:
        scratchpad = self.state_manager.get_react_scratchpad()
        scratchpad.setdefault("timeline", [])
        return scratchpad

    def _get_base_prompt(self) -> str:
        prompt_file = Path(__file__).parent / "prompts" / "react_prompt.xml"
        if prompt_file.exists():
            try:
                tree = ET.parse(prompt_file)
                root = tree.getroot()
                description = root.find("description")
                if description is not None and description.text:
                    return description.text.strip()
            except Exception:
                pass
        return "Use this tool to record think/observe notes and manage the react scratchpad"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        prompt_file = Path(__file__).parent / "prompts" / "react_prompt.xml"
        if prompt_file.exists():
            try:
                tree = ET.parse(prompt_file)
                root = tree.getroot()
                parameters = root.find("parameters")
                if parameters is not None:
                    schema: Dict[str, Any] = {
                        "type": "object",
                        "properties": {},
                        "required": ["action"],
                    }
                    for param in parameters.findall("parameter"):
                        name = param.get("name")
                        param_type = param.find("type")
                        description = param.find("description")
                        if name and param_type is not None:
                            schema["properties"][name] = {
                                "type": param_type.text.strip(),
                                "description": description.text.strip()
                                if description is not None and description.text
                                else "",
                            }
                    return schema
            except Exception:
                pass
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "react operation to perform",
                },
                "thoughts": {
                    "type": "string",
                    "description": "Thought content for think action",
                },
                "next_action": {
                    "type": "string",
                    "description": "Planned next action for think action",
                },
                "result": {
                    "type": "string",
                    "description": "Observation message for observe action",
                },
            },
            "required": ["action"],
        }
