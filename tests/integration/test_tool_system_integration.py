"""Integration tests for the unified tool system."""

from unittest.mock import patch

import pytest

from tunacode.tools.decorator import tool_definition
from tunacode.tools.feature_flags import ToolFeatureFlags
from tunacode.tools.openai_formatter import OpenAIFormatter
from tunacode.tools.prompt_generator import PromptGenerator
from tunacode.tools.registry import ToolCategory, ToolRegistry
from tunacode.tools.system_builder import SystemPromptBuilder


class TestToolSystemIntegration:
    """Integration tests for the complete unified tool system."""

    def setup_method(self):
        """Setup for each test."""
        ToolRegistry.clear()
        ToolFeatureFlags.disable_all_migration()

    def teardown_method(self):
        """Cleanup after each test."""
        ToolRegistry.clear()
        ToolFeatureFlags.disable_all_migration()

    def test_end_to_end_tool_workflow(self):
        """Test complete workflow from tool definition to prompt generation."""

        # Step 1: Define a tool with decorator
        @tool_definition(
            name="integration_test_tool",
            category=ToolCategory.READ_ONLY,
            description="A tool for integration testing",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Result limit"},
                },
                "required": ["query"],
            },
            example_args={"query": "test", "limit": 10},
            brief="Integration test tool",
        )
        class IntegrationTestTool:
            pass

        # Step 2: Verify registration
        definition = ToolRegistry.get("integration_test_tool")
        assert definition is not None
        assert definition.name == "integration_test_tool"

        # Step 3: Generate documentation
        docs = PromptGenerator.generate_tool_documentation(definition)
        assert "integration_test_tool" in docs
        assert "A tool for integration testing" in docs

        # Step 4: Generate OpenAI format
        formatted = OpenAIFormatter.format_tool_call(
            "integration_test_tool", {"query": "test", "limit": 5}
        )
        assert "tool_calls" in formatted
        assert formatted["tool_calls"][0]["function"]["name"] == "integration_test_tool"

        # Step 5: Validate format
        assert OpenAIFormatter.validate_format(formatted) is True

    def test_feature_flag_integration(self):
        """Test that feature flags properly control system behavior."""

        # Register a test tool
        @tool_definition(
            name="flag_test_tool",
            category=ToolCategory.READ_ONLY,
            description="Tool for testing flags",
            parameters={"type": "object", "properties": {}},
        )
        class FlagTestTool:
            pass

        # Test with flags disabled (default)
        assert ToolFeatureFlags.use_unified_registry() is False
        assert ToolFeatureFlags.use_dynamic_prompts() is False

        # Enable flags
        ToolFeatureFlags.enable_full_migration()
        assert ToolFeatureFlags.use_unified_registry() is True
        assert ToolFeatureFlags.use_dynamic_prompts() is True
        assert ToolFeatureFlags.disable_xml_loading() is True

        # Test migration status
        status = ToolFeatureFlags.get_migration_status()
        assert status["unified_registry"] is True
        assert status["dynamic_prompts"] is True
        assert status["xml_disabled"] is True

    def test_prompt_generation_with_multiple_tools(self):
        """Test prompt generation with multiple tools in different categories."""

        # Register tools in different categories
        @tool_definition(
            name="read_tool",
            category=ToolCategory.READ_ONLY,
            description="Read operation tool",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        class ReadTool:
            pass

        @tool_definition(
            name="write_tool",
            category=ToolCategory.WRITE,
            description="Write operation tool",
            parameters={"type": "object", "properties": {"content": {"type": "string"}}},
        )
        class WriteTool:
            pass

        @tool_definition(
            name="execute_tool",
            category=ToolCategory.EXECUTE,
            description="Execute operation tool",
            parameters={"type": "object", "properties": {"command": {"type": "string"}}},
        )
        class ExecuteTool:
            pass

        # Generate complete documentation
        all_docs = PromptGenerator.generate_all_tools()

        # Verify all tools are included
        assert "read_tool" in all_docs
        assert "write_tool" in all_docs
        assert "execute_tool" in all_docs

        # Verify category sections
        assert "Read-Only Tools" in all_docs
        assert "File Modification Tools" in all_docs
        assert "System Execution Tools" in all_docs

        # Generate parallel rules
        rules = PromptGenerator.generate_parallel_rules()
        assert "read_tool" in rules
        assert "Parallel-safe" in rules
        assert "sequential only" in rules

    def test_system_prompt_building(self):
        """Test system prompt building with tool integration."""

        # Register a test tool
        @tool_definition(
            name="prompt_test_tool",
            category=ToolCategory.TASK_MGMT,
            description="Tool for prompt testing",
            parameters={"type": "object", "properties": {}},
        )
        class PromptTestTool:
            pass

        # Test with mock base prompt
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                "Base system prompt with {TOOLS_DOCUMENTATION} placeholder"
            )

            # Build system prompt with tools
            prompt = SystemPromptBuilder.build_system_prompt(include_tools=True)

            # Should contain tool documentation
            assert "prompt_test_tool" in prompt
            assert "Tool for prompt testing" in prompt

    def test_openai_format_round_trip(self):
        """Test OpenAI format creation and parsing round trip."""
        original_calls = [
            ("tool1", {"param1": "value1", "param2": 42}),
            ("tool2", {"param3": True, "param4": [1, 2, 3]}),
        ]

        # Format multiple calls
        formatted = OpenAIFormatter.format_multiple_tool_calls(original_calls)

        # Convert to JSON and back (simulating API round trip)
        import json

        json_str = json.dumps(formatted)
        parsed = OpenAIFormatter.parse_tool_response(json_str)

        # Verify data integrity
        assert len(parsed["tool_calls"]) == 2

        call1 = parsed["tool_calls"][0]
        assert call1["function"]["name"] == "tool1"
        assert call1["function"]["arguments"]["param1"] == "value1"
        assert call1["function"]["arguments"]["param2"] == 42

        call2 = parsed["tool_calls"][1]
        assert call2["function"]["name"] == "tool2"
        assert call2["function"]["arguments"]["param3"] is True
        assert call2["function"]["arguments"]["param4"] == [1, 2, 3]

    def test_registry_category_filtering(self):
        """Test registry category filtering for execution policies."""
        # Register tools in different categories
        categories_tools = [
            (ToolCategory.READ_ONLY, "read1"),
            (ToolCategory.READ_ONLY, "read2"),
            (ToolCategory.WRITE, "write1"),
            (ToolCategory.EXECUTE, "exec1"),
            (ToolCategory.TASK_MGMT, "task1"),
        ]

        for category, name in categories_tools:

            @tool_definition(
                name=name,
                category=category,
                description=f"Tool {name}",
                parameters={"type": "object", "properties": {}},
            )
            class DynamicTool:
                pass

        # Test category filtering
        read_only_tools = ToolRegistry.get_by_category(ToolCategory.READ_ONLY)
        assert len(read_only_tools) == 2
        assert {t.name for t in read_only_tools} == {"read1", "read2"}

        write_tools = ToolRegistry.get_by_category(ToolCategory.WRITE)
        assert len(write_tools) == 1
        assert write_tools[0].name == "write1"

        execute_tools = ToolRegistry.get_by_category(ToolCategory.EXECUTE)
        assert len(execute_tools) == 1
        assert execute_tools[0].name == "exec1"

        task_tools = ToolRegistry.get_by_category(ToolCategory.TASK_MGMT)
        assert len(task_tools) == 1
        assert task_tools[0].name == "task1"


if __name__ == "__main__":
    pytest.main([__file__])
