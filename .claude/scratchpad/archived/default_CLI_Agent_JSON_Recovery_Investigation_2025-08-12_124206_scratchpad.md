# CLI Agent JSON Recovery Investigation
_Started: 2025-08-12 12:34:05_
_Agent: default

[1] Problem: CLI agent failed with Invalid JSON Extra data error when model emitted multiple concatenated JSON objects as tool args. Retry mechanism did not trigger.
[2] [1] Found parse_args in src/tunacode/cli/repl_components/command_parser.py:13-34 - uses strict json.loads() which rejects concatenated JSON objects
[3] [2] Tool executor calls parse_args at src/tunacode/cli/repl_components/tool_executor.py:59 - failure happens here before any recovery attempt
[4] [3] Error recovery at src/tunacode/cli/repl_components/error_recovery.py:19-88 filters by keywords (tool/function/call/schema) on line 26-29
[3~1] [3~1] Recovery returns False immediately if error message lacks these keywords - JSON errors typically do not contain them
[5] [4] Recovery is called from repl.py:372 in generic exception handler - only executes if attempt_tool_recovery returns True
[6] [5] When json.loads() fails with Extra data, JSONDecodeError is raised and caught at line 29, then re-raised as ValidationError with Invalid JSON prefix
[7] [6] Recovery calls extract_and_execute_tool_calls which parses tool calls from plain text content - designed for text-dumped tools, not malformed args in structured tool calls
[8] [7] Example of malformed args: {"filepath": "main.py"}{"filepath": "__init__.py"}{"filepath": "cli/main.py"} - multiple JSON objects concatenated
[9] [8] Root cause: Model violated tool calling contract by emitting multiple JSON objects for a single tool call instead of one object or array
[10] [9] Why recovery failed: (1) Error message lacked keywords tool/function/call/schema (2) Recovery designed for text-dumped tools not malformed structured args
[11] [10] Recommendations: (1) Update prompts to enforce single JSON object per args (2) Broaden recovery keywords to include json/jsondecodeerror (3) Consider NDJSON splitter for read-only tools
