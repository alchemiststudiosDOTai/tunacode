"""Unit tests for the prompt generator."""

from unittest.mock import Mock

import pytest

from tunacode.tools.prompt_generator import PromptGenerator
from tunacode.tools.registry import ToolCategory, ToolDefinition, ToolRegistry


class TestPromptGenerator:
    """Test cases for PromptGenerator functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        ToolRegistry.clear()

    def test_generate_tool_example_with_args(self):
        """Test generating examples when tool has example_args."""
        tool = ToolDefinition(
            name="test_tool",
            category=ToolCategory.READ_ONLY,
            description="Test tool",
            parameters={},
            example_args={"pattern": "*.py", "directory": "src/"},
            tool_class=Mock(),
        )

        example = PromptGenerator.generate_tool_example(tool)

        assert "test_tool" in example
        assert "*.py" in example
        assert "src/" in example
        assert "tool_calls" in example

    def test_generate_tool_example_from_required(self):
        """Test generating examples from required parameters."""
        tool = ToolDefinition(
            name="test_tool",
            category=ToolCategory.READ_ONLY,
            description="Test tool",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "count": {"type": "integer"},
                    "enabled": {"type": "boolean"},
                },
                "required": ["query", "count"],
            },
            tool_class=Mock(),
        )

        example = PromptGenerator.generate_tool_example(tool)

        assert "example_query" in example
        assert "1" in example or '"count": 1' in example

    def test_generate_parallel_rules(self):
        """Test generating parallel execution rules."""
        # Register tools in different categories
        read_tool = ToolDefinition(
            name="read_tool",
            category=ToolCategory.READ_ONLY,
            description="Read tool",
            parameters={},
            tool_class=Mock(),
        )

        write_tool = ToolDefinition(
            name="write_tool",
            category=ToolCategory.WRITE,
            description="Write tool",
            parameters={},
            tool_class=Mock(),
        )

        execute_tool = ToolDefinition(
            name="execute_tool",
            category=ToolCategory.EXECUTE,
            description="Execute tool",
            parameters={},
            tool_class=Mock(),
        )

        ToolRegistry.register(read_tool)
        ToolRegistry.register(write_tool)
        ToolRegistry.register(execute_tool)

        rules = PromptGenerator.generate_parallel_rules()

        assert "read_tool" in rules
        assert "write_tool" in rules
        assert "execute_tool" in rules
        assert "Parallel-safe" in rules
        assert "sequential only" in rules

    def test_generate_tool_documentation(self):
        """Test generating documentation for a single tool."""
        tool = ToolDefinition(
            name="example_tool",
            category=ToolCategory.READ_ONLY,
            description="An example tool for testing",
            parameters={
                "type": "object",
                "properties": {
                    "required_param": {"type": "string", "description": "A required parameter"},
                    "optional_param": {"type": "integer", "description": "An optional parameter"},
                },
                "required": ["required_param"],
            },
            brief="Brief description",
            example_args={"required_param": "test"},
            tool_class=Mock(),
        )

        docs = PromptGenerator.generate_tool_documentation(tool)

        assert "## example_tool" in docs
        assert "An example tool for testing" in docs
        assert "Brief description" in docs
        assert "required_param" in docs
        assert "(required)" in docs
        assert "(optional)" in docs
        assert "**Example:**" in docs

    def test_generate_all_tools_empty(self):
        """Test generating docs when no tools are registered."""
        docs = PromptGenerator.generate_all_tools()
        assert "No tools registered" in docs

    def test_generate_all_tools_with_categories(self):
        """Test generating docs with tools in different categories."""
        # Register tools in different categories
        read_tool = ToolDefinition(
            name="read_tool",
            category=ToolCategory.READ_ONLY,
            description="Read tool",
            parameters={"type": "object", "properties": {}},
            tool_class=Mock(),
        )

        task_tool = ToolDefinition(
            name="task_tool",
            category=ToolCategory.TASK_MGMT,
            description="Task tool",
            parameters={"type": "object", "properties": {}},
            tool_class=Mock(),
        )

        ToolRegistry.register(read_tool)
        ToolRegistry.register(task_tool)

        docs = PromptGenerator.generate_all_tools()

        assert "# Available Tools" in docs
        assert "Read-Only Tools" in docs
        assert "Task Management Tools" in docs
        assert "read_tool" in docs
        assert "task_tool" in docs


if __name__ == "__main__":
    pytest.main([__file__])
