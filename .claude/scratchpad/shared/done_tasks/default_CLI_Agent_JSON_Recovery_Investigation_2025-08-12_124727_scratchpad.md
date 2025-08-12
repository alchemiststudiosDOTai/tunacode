# CLI Agent JSON Recovery Investigation
_Started: 2025-08-12 12:44:03_
_Agent: default

[1] [1] Found command_parser.py:13-34 - strict JSON parsing with json.loads()
[2] [2] Found tool_executor.py:59 - calls parse_args() which throws ValidationError
[3] [3] Found error_recovery.py:26-29 - keyword filtering excludes Invalid JSON errors
[4] [4] Key issue: error_recovery.py only triggers on tool, function, call, schema keywords
[5] [5] Recovery mechanism only parses tools from message content, not malformed args
[6] [6] Found existing retry.py utility with retry_on_json_error decorator
[7] [7] System prompt in src/tunacode/prompts/system.md defines tool behavior instructions
[8] [8] parse_json_tool_calls already has retry logic with 10 attempts
[9] [9] Problem: parse_args in command_parser.py does not use retry logic, fails immediately
