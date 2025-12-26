# OpenAI Tool Schemas

This document describes the OpenAI-compatible function calling schemas for Tunacode tools.

## Overview

Tunacode uses Pydantic-AI for internal tool handling, which auto-generates schemas from Python function signatures. The `openai_tool_schemas.json` file in this directory provides the equivalent schemas in OpenAI's function calling format for interoperability.

## Schema Format

Each tool follows the OpenAI function calling specification:

```json
{
  "type": "function",
  "function": {
    "name": "tool_name",
    "description": "What the tool does",
    "parameters": {
      "type": "object",
      "properties": {
        "param_name": {
          "type": "string",
          "description": "Parameter description"
        }
      },
      "required": ["param_name"]
    }
  }
}
```

## Tools

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `bash` | Execute bash commands | `command` |
| `glob` | Find files by pattern | `pattern` |
| `grep` | Search file contents | `pattern` |
| `list_dir` | List directory tree | (none) |
| `read_file` | Read file contents | `filepath` |
| `update_file` | Replace text in file | `filepath`, `target`, `patch` |
| `write_file` | Create new file | `filepath`, `content` |
| `web_fetch` | Fetch URL content | `url` |
| `todowrite` | Update task list | `todos` |
| `todoread` | Read task list | (none) |
| `todoclear` | Clear task list | (none) |

## Strict Mode (Optional)

OpenAI introduced strict mode in 2024 for guaranteed schema compliance. To enable:

```json
{
  "type": "function",
  "function": {
    "name": "bash",
    "strict": true,
    "description": "Execute a bash command",
    "parameters": {
      "type": "object",
      "properties": { ... },
      "required": ["command"],
      "additionalProperties": false
    }
  }
}
```

Requirements for strict mode:
- Set `"strict": true` in the function object
- Set `"additionalProperties": false` in parameters
- All properties should be in the `required` array (use nullable types for optional fields)

## Usage

The JSON file can be used directly with OpenAI's Chat Completions API:

```python
import json

with open("docs/openai_tool_schemas.json") as f:
    schemas = json.load(f)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[...],
    tools=schemas["tools"]
)
```

## Source

These schemas are derived from the tool implementations in `src/tunacode/tools/`:
- `bash.py`
- `glob.py`
- `grep.py`
- `list_dir.py`
- `read_file.py`
- `update_file.py`
- `write_file.py`
- `web_fetch.py`
- `todo.py`
