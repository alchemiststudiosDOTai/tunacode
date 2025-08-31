"""Unit tests for the unified tool registry."""

from unittest.mock import Mock

import pytest

from tunacode.tools.decorator import tool_definition
from tunacode.tools.registry import ToolCategory, ToolDefinition, ToolRegistry


class TestToolRegistry:
    """Test cases for ToolRegistry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        ToolRegistry.clear()

    def test_register_and_get_tool(self):
        """Test basic tool registration and retrieval."""
        # Create a mock tool class
        mock_tool = Mock()

        definition = ToolDefinition(
            name="test_tool",
            category=ToolCategory.READ_ONLY,
            description="Test tool description",
            parameters={"type": "object", "properties": {}},
            tool_class=mock_tool,
        )

        ToolRegistry.register(definition)

        # Test retrieval
        retrieved = ToolRegistry.get("test_tool")
        assert retrieved is not None
        assert retrieved.name == "test_tool"
        assert retrieved.category == ToolCategory.READ_ONLY
        assert retrieved.tool_class == mock_tool

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        result = ToolRegistry.get("nonexistent")
        assert result is None

    def test_get_by_category(self):
        """Test filtering tools by category."""
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

        ToolRegistry.register(read_tool)
        ToolRegistry.register(write_tool)

        # Test category filtering
        read_only_tools = ToolRegistry.get_by_category(ToolCategory.READ_ONLY)
        assert len(read_only_tools) == 1
        assert read_only_tools[0].name == "read_tool"

        write_tools = ToolRegistry.get_by_category(ToolCategory.WRITE)
        assert len(write_tools) == 1
        assert write_tools[0].name == "write_tool"

    def test_get_all_tools(self):
        """Test getting all registered tools."""
        # Initially empty
        assert len(ToolRegistry.get_all()) == 0

        # Register some tools
        for i in range(3):
            definition = ToolDefinition(
                name=f"tool_{i}",
                category=ToolCategory.READ_ONLY,
                description=f"Tool {i}",
                parameters={},
                tool_class=Mock(),
            )
            ToolRegistry.register(definition)

        all_tools = ToolRegistry.get_all()
        assert len(all_tools) == 3
        assert {t.name for t in all_tools} == {"tool_0", "tool_1", "tool_2"}

    def test_clear_registry(self):
        """Test clearing the registry."""
        # Register a tool
        definition = ToolDefinition(
            name="test_tool",
            category=ToolCategory.READ_ONLY,
            description="Test",
            parameters={},
            tool_class=Mock(),
        )
        ToolRegistry.register(definition)

        assert len(ToolRegistry.get_all()) == 1

        # Clear and verify
        ToolRegistry.clear()
        assert len(ToolRegistry.get_all()) == 0
        assert ToolRegistry.get("test_tool") is None


class TestToolDecorator:
    """Test cases for the @tool_definition decorator."""

    def setup_method(self):
        """Clear registry before each test."""
        ToolRegistry.clear()

    def test_decorator_registers_tool(self):
        """Test that the decorator automatically registers tools."""

        @tool_definition(
            name="decorated_tool",
            category=ToolCategory.EXECUTE,
            description="A decorated tool",
            parameters={"type": "object", "properties": {"arg": {"type": "string"}}},
        )
        class DecoratedTool:
            pass

        # Check that it was registered
        definition = ToolRegistry.get("decorated_tool")
        assert definition is not None
        assert definition.name == "decorated_tool"
        assert definition.category == ToolCategory.EXECUTE
        assert definition.tool_class == DecoratedTool

        # Check that the class has the definition attached
        assert hasattr(DecoratedTool, "_tool_definition")
        assert DecoratedTool._tool_definition == definition

    def test_decorator_with_optional_params(self):
        """Test decorator with optional parameters."""

        @tool_definition(
            name="optional_tool",
            category=ToolCategory.READ_ONLY,
            description="Tool with optional params",
            parameters={"type": "object"},
            example_args={"test": "value"},
            brief="Brief description",
            examples=[("Example 1", "example code")],
        )
        class OptionalTool:
            pass

        definition = ToolRegistry.get("optional_tool")
        assert definition.example_args == {"test": "value"}
        assert definition.brief == "Brief description"
        assert definition.examples == [("Example 1", "example code")]


class TestToolDefinition:
    """Test cases for ToolDefinition dataclass."""

    def test_tool_definition_creation(self):
        """Test creating a ToolDefinition."""
        mock_class = Mock()

        definition = ToolDefinition(
            name="test",
            category=ToolCategory.TASK_MGMT,
            description="Test description",
            parameters={"type": "object"},
            tool_class=mock_class,
            example_args={"arg": "value"},
            brief="Brief",
            examples=[("ex1", "code1")],
        )

        assert definition.name == "test"
        assert definition.category == ToolCategory.TASK_MGMT
        assert definition.description == "Test description"
        assert definition.parameters == {"type": "object"}
        assert definition.tool_class == mock_class
        assert definition.example_args == {"arg": "value"}
        assert definition.brief == "Brief"
        assert definition.examples == [("ex1", "code1")]

    def test_tool_definition_defaults(self):
        """Test ToolDefinition with default values."""
        definition = ToolDefinition(
            name="minimal",
            category=ToolCategory.READ_ONLY,
            description="Minimal tool",
            parameters={},
            tool_class=Mock(),
        )

        assert definition.example_args is None
        assert definition.brief is None
        assert definition.examples is None


if __name__ == "__main__":
    pytest.main([__file__])
