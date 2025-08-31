"""Prompt generation from tool registry.

This module generates tool documentation and examples from the unified registry
instead of hardcoded system.md content.
"""

import json
from typing import Dict, List

from .registry import ToolCategory, ToolDefinition, ToolRegistry


class PromptGenerator:
    """Generates prompts and documentation from tool registry."""

    @staticmethod
    def generate_tool_example(tool: ToolDefinition) -> str:
        """Generate OpenAI function call example per new_prompt.xml format.

        Args:
            tool: Tool definition with example arguments

        Returns:
            JSON example string in OpenAI function call format
        """
        if not tool.example_args:
            # Generate minimal example from required parameters
            example_args = {}
            if tool.parameters.get("required"):
                for param in tool.parameters["required"]:
                    prop = tool.parameters.get("properties", {}).get(param, {})
                    if prop.get("type") == "string":
                        example_args[param] = f"example_{param}"
                    elif prop.get("type") == "boolean":
                        example_args[param] = "true"
                    elif prop.get("type") == "integer":
                        example_args[param] = "1"
                    else:
                        example_args[param] = "example_value"
        else:
            example_args = tool.example_args

        example = {
            "tool_calls": [
                {
                    "id": f"call_{tool.name.lower()}",
                    "type": "function",
                    "function": {"name": tool.name, "arguments": json.dumps(example_args)},
                }
            ]
        }
        return f"```json\n{json.dumps(example, indent=2)}\n```"

    @staticmethod
    def generate_parallel_rules() -> str:
        """Generate execution rules for parallel vs sequential tools."""
        read_only = [t.name for t in ToolRegistry.get_by_category(ToolCategory.READ_ONLY)]
        write_tools = [t.name for t in ToolRegistry.get_by_category(ToolCategory.WRITE)]
        execute_tools = [t.name for t in ToolRegistry.get_by_category(ToolCategory.EXECUTE)]

        rules = []
        if read_only:
            rules.append(
                f"**Parallel-safe tools (can be called together):** {', '.join(read_only)}"
            )
        if write_tools:
            rules.append(f"**Write tools (sequential only):** {', '.join(write_tools)}")
        if execute_tools:
            rules.append(f"**Execute tools (sequential only):** {', '.join(execute_tools)}")

        return "\n".join(rules)

    @staticmethod
    def generate_tool_documentation(tool: ToolDefinition) -> str:
        """Generate documentation for a single tool.

        Args:
            tool: Tool definition to document

        Returns:
            Formatted tool documentation
        """
        lines = []
        lines.append(f"## {tool.name}")
        lines.append("")
        lines.append(tool.description)
        lines.append("")

        if tool.brief:
            lines.append(f"**Brief:** {tool.brief}")
            lines.append("")

        # Parameters
        if tool.parameters.get("properties"):
            lines.append("**Parameters:**")
            for param, spec in tool.parameters["properties"].items():
                required = param in tool.parameters.get("required", [])
                req_text = " (required)" if required else " (optional)"
                lines.append(f"- `{param}`: {spec.get('description', 'No description')}{req_text}")
            lines.append("")

        # Example
        if tool.example_args or tool.parameters.get("required"):
            lines.append("**Example:**")
            lines.append(PromptGenerator.generate_tool_example(tool))
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def generate_all_tools() -> str:
        """Generate documentation for all registered tools."""
        tools = ToolRegistry.get_all()
        if not tools:
            return "No tools registered."

        # Group by category
        by_category: Dict[ToolCategory, List[ToolDefinition]] = {}
        for tool in tools:
            if tool.category not in by_category:
                by_category[tool.category] = []
            by_category[tool.category].append(tool)

        lines = []
        lines.append("# Available Tools")
        lines.append("")
        lines.append(PromptGenerator.generate_parallel_rules())
        lines.append("")

        # Generate docs by category
        category_names = {
            ToolCategory.READ_ONLY: "Read-Only Tools",
            ToolCategory.WRITE: "File Modification Tools",
            ToolCategory.EXECUTE: "System Execution Tools",
            ToolCategory.TASK_MGMT: "Task Management Tools",
            ToolCategory.PLANNING: "Planning Tools",
        }

        for category, category_tools in by_category.items():
            lines.append(f"# {category_names.get(category, category.value.title())} Tools")
            lines.append("")

            for tool in sorted(category_tools, key=lambda t: t.name):
                lines.append(PromptGenerator.generate_tool_documentation(tool))

        return "\n".join(lines)
