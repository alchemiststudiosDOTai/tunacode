"""Test suite for unified tool system - verifies registry, schemas, and OpenAI format"""

import json

from tunacode.tools.bash import BashTool

# Import tools to trigger registration
from tunacode.tools.grep import ParallelGrep
from tunacode.tools.openai_formatter import OpenAIFormatter
from tunacode.tools.read_file import ReadFileTool
from tunacode.tools.registry import ToolRegistry
from tunacode.tools.schema_assembler import ToolSchemaAssembler


def test_tool_registration_and_schemas():
    """Test that all tools are registered and generate correct schemas"""
    # Get all registered tools
    tools = ToolRegistry.get_all()

    # Verify we have the expected number of tools
    assert len(tools) >= 9, f"Expected at least 9 tools, got {len(tools)}"

    # Check each tool has required fields
    for definition in tools:
        assert definition.name
        assert definition.category is not None
        assert definition.description
        assert definition.parameters
        assert "properties" in definition.parameters
        assert definition.tool_class is not None

    # Test schema generation for a specific tool
    assembler = ToolSchemaAssembler()
    grep_schema = assembler.get_tool_schema("grep")
    assert grep_schema is not None
    assert grep_schema["name"] == "grep"
    assert "pattern" in grep_schema["parameters"]["properties"]


def test_openai_format_stringified_arguments():
    """Test OpenAI function format with stringified arguments"""
    formatter = OpenAIFormatter()

    # Test formatting a tool call
    args = {"pattern": "test.*", "path": "/src", "output_mode": "content"}
    result = formatter.format_tool_call("grep", args)

    # Verify structure
    assert "tool_calls" in result
    assert len(result["tool_calls"]) == 1
    call = result["tool_calls"][0]
    assert call["type"] == "function"
    assert call["function"]["name"] == "grep"

    # CRITICAL: Verify arguments are stringified
    assert isinstance(call["function"]["arguments"], str)
    parsed_args = json.loads(call["function"]["arguments"])
    assert parsed_args == args

    # Test round-trip parsing
    response_json = json.dumps(result)
    parsed = formatter.parse_tool_response(response_json)
    assert parsed["tool_calls"][0]["function"]["arguments"] == args


def test_registry_replaces_xml():
    """Test that registry is used instead of XML for all tools"""
    # Verify tools have registry definitions
    for tool_class in [ParallelGrep, BashTool, ReadFileTool]:
        tool = tool_class()
        schema = tool.get_tool_schema()

        # Schema should come from registry
        assert schema is not None
        assert "name" in schema
        assert "parameters" in schema

        # Verify no XML references
        assert not hasattr(tool, "_load_xml_prompt")
        assert not hasattr(tool, "xml_prompt")

    # Verify XML helper is not imported anywhere
    import os

    assert not os.path.exists("src/tunacode/tools/xml_helper.py")
    assert not os.path.exists("src/tunacode/tools/prompts/")
