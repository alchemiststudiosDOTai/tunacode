# Tool Format Bug Investigation
_Started: 2025-08-31 17:23:23_
_Agent: bug-context-analyzer

[1] [1] System prompt analysis: Found explicit OpenAI format instructions with file_path parameter on line 45
[2] [2] Found schema assembler that uses ToolRegistry.get() and falls back to tool.get_tool_schema()
[3] [3] ReadFileTool shows correct file_path parameter in decorator definition (line 38) and schema (line 127)
[4] [4] Agent config uses pydantic-ai Tool() wrapper which bypasses TunaCode tool registry and schemas
[5] [5] Found pydantic-ai bypasses TunaCode schemas. Tool() wraps functions directly, uses function signatures for API schemas
[6] [6] CRITICAL: Function signature uses "filepath" parameter but system prompt shows "file_path" - this is the source of the disconnect\!
[7] [7] Pattern confirmed: Tool classes have file_path, but pydantic-ai wrapper functions use filepath - mismatch\!
[8] [8] Execution path: Agent uses pydantic_ai.Tool(read_file) -> pydantic-ai introspects function signature -> sends "filepath" to API despite system prompt saying "file_path"
[9] [9] TunaCode has complete tool registry with correct schemas but pydantic-ai bypasses it entirely by wrapping standalone functions
