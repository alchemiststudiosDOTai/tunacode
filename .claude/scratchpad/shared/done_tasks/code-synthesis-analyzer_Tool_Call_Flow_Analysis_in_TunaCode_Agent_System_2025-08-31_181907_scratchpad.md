# Tool Call Flow Analysis in TunaCode Agent System
_Started: 2025-08-31 18:16:56_
_Agent: code-synthesis-analyzer

[1] Found main.py - uses pydantic_ai.Agent directly, imports tools but has lazy imports to avoid circular dependencies
[2] Found json_tool_parser.py - fallback JSON parsing system for when structured tool calling fails. Creates MockToolCall objects to match API format
[3] Found agent_config.py - Creates pydantic_ai.Agent with Tool() wrappers. Line 270-275 shows Agent creation with model, system_prompt, tools=tools_list, mcp_servers
[4] Found system.xml - System prompt mandates OpenAI function calling format with JSON tool_calls arrays. Lines 14-31 show exact expected format: tool_calls[].function.arguments must be JSON string
[5] Found node_processor.py - Lines 306-442 process tool calls from node.model_response.parts where part.part_kind == tool-call. Uses part.tool_name and part.args directly from pydantic-ai structure
[6] Found tool_handler.py - Tool confirmation logic only, no API or schema handling. Not involved in API request formation
[7] Found read_file.py - Uses @tool_definition decorator to define JSON schema (lines 31-55). Has _get_parameters_schema() method that returns pydantic-compatible JSON schema from decorator. Function read_file() is wrapped by pydantic_ai.Tool()
[8] Found decorator.py - @tool_definition creates ToolDefinition with JSON schema and registers in ToolRegistry. Sets _tool_definition attribute on class containing parameters schema
[9] Found openai_formatter.py - Has utilities to format tool calls in OpenAI function call format. BUT this appears to be utility code, not used in actual API calls. Still need to find where pydantic-ai sends schemas to API
[10] Found pydantic_ai imports - System uses pydantic_ai.Agent and Tool directly. No custom API handler layer found. Tool schemas must be handled internally by pydantic-ai
[11] Found PYDANTIC_TOOL_INTEGRATION.md - Comprehensive analysis document. Lines 453-454 reveal KEY INSIGHT: pydantic-ai uses wrapper function signatures automatically for schema generation, not manual JSON schemas
[12] Ready to synthesize findings. Key discovery: TunaCode uses pydantic-ai.Tool() wrappers around async functions, and pydantic-ai automatically generates OpenAI-compatible schemas from function signatures, not from the @tool_definition JSON schemas
