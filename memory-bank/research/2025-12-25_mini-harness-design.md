# Research - Mini Harness Design for TunaCode Evals

**Date:** 2025-12-25
**Owner:** claude
**Phase:** Research

## Goal

Summarize existing evals harness and real agent implementation to anchor mini harness design with faithful Qwen2.5 parser and tool-call format.

---

## Findings

### 1. Existing Evals Harness Structure

| File | Purpose |
|------|---------|
| `evals/agent_eval.py` | Main eval runner with retry logic |
| `evals/parser.py` | Multi-strategy tool call parser |
| `evals/tools.py` | 8 tool schemas (OpenAI function calling format) |
| `evals/config.py` | Configuration constants |
| `evals/scenarios.json` | 34 test cases (prompt, expected tool, expected args) |
| `evals/systemPrompt.md` | Full TunaCode system prompt |

### 2. Eval Loop Pattern (agent_eval.py:38-65)

```
for attempt in range(1, MAX_ATTEMPTS + 1):
    response = client.chat.completions.create(...)
    tool, args = parse_tool_call(message, ALLOWED_TOOLS)
    if tool:
        break
    if attempt < MAX_ATTEMPTS:
        messages.append(assistant_content)
        messages.append(RETRY_PROMPT.format(task=prompt))
```

**Key behaviors:**
- MAX_ATTEMPTS = 2 (one initial + one retry)
- Retry prompt: "No valid tool call found. Slow down. Think step by step."
- Pass condition: `tool == expected_tool AND all expected_args match`

### 3. Qwen2.5 Parser Strategies (parser.py:62-110)

**Strategy 1: OpenAI tool_calls** (structured API response)
```python
if msg.tool_calls:
    tc = msg.tool_calls[0]
    return tc.function.name, tc.function.arguments
```

**Strategy 2: XML tags**
```python
TOOL_XML_RE = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
# Extract JSON from inside tags
```

**Strategy 3: Raw JSON regex**
```python
TOOL_JSON_RE = r'\{"name":\s*"([^"]+)",\s*"arguments":\s*(\{[^}]*\})\}'
# Match bare {"name": "...", "arguments": {...}}
```

**Strategy 4: Fallback parser** (BROKEN - missing import)
```python
from tunacode_training.eval.parser import extract_tool_call  # DNE
```

### 4. Tool Schema Format (tools.py)

OpenAI function calling format:
```python
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read contents of a file",
        "parameters": {
            "type": "object",
            "properties": {"filepath": {"type": "string", ...}},
            "required": ["filepath"]
        }
    }
}
```

8 tools: `bash`, `glob`, `grep`, `list_dir`, `read_file`, `update_file`, `web_fetch`, `write_file`

### 5. Real Agent Implementation (src/tunacode/core/)

**Tool Call Flow:**
1. Pydantic-ai parses model response into nodes with `part_kind="tool-call"`
2. Tools categorized: research / read-only / write-execute
3. Execution order: research first, read-only parallel, write sequential
4. Retry: exponential backoff up to TOOL_MAX_RETRIES=3

**Key files:**
- `agents/main.py:527-545` - Request orchestration
- `agents/agent_components/node_processor.py:270-386` - Tool execution
- `agents/agent_components/tool_executor.py:44-101` - Parallel + retry
- `agents/agent_components/agent_config.py:385-408` - Tool registration

### 6. Real Tool Definition Pattern (src/tunacode/tools/)

```python
@file_tool
async def read_file(filepath: str, offset: int = 0, limit: int | None = None) -> str:
    """Read the contents of a file with line limiting."""
    ...
```

- `@base_tool`: Error handling wrapper
- `@file_tool`: File-specific errors + LSP diagnostics
- Pydantic-ai auto-generates schemas from signatures
- XML prompts in `tools/prompts/{name}_prompt.xml` override docstrings

---

## Key Patterns / Solutions Found

| Pattern | Description | Relevance |
|---------|-------------|-----------|
| Multi-strategy parsing | Try OpenAI > XML > JSON > fallback | Essential for Qwen2.5 compatibility |
| Retry with prompt | Append error context + retry instruction | Improves tool call success rate |
| Path normalization | Strip trailing `/` from directory/filepath | Prevents false negatives |
| Truncation detection | Check for `...` or unmatched code fences | Enables retry on incomplete output |
| Tool validation | Check name in allowed set, args is dict | Prevents execution of invalid calls |

---

## Knowledge Gaps

1. **Missing fallback parser**: `tunacode_training.eval.parser.extract_tool_call` does not exist - needs implementation
2. **Code fence extraction**: Strategy for ```` ```json {...} ``` ```` format not fully implemented
3. **Argument type coercion**: Current parser doesn't validate/coerce arg types to match schema

---

## Mini Harness Design Requirements

Based on research, the mini harness must implement:

### Core Loop
1. Load system prompt from file
2. Load scenarios from JSON
3. For each test: run up to MAX_ATTEMPTS with retry prompt
4. Parse tool call using multi-strategy parser
5. Compare tool name + args against expected
6. Report pass/fail with attempt count

### Parser Strategies (in order)
1. `msg.tool_calls[0]` - OpenAI structured
2. `<tool_call>{...}</tool_call>` - XML wrapper
3. `{"name": "...", "arguments": {...}}` - Raw JSON
4. ` ```json {...} ``` ` - Code fence (NEW)
5. Loose JSON with name/arguments keys (NEW)

### Tool Schema
- Use existing `tools.py` (8 tools, OpenAI format)
- Pass to API via `tools=TOOLS` parameter

### Configuration
- `MAX_ATTEMPTS = 2`
- `MAX_TOKENS = 300`
- `RETRY_PROMPT = "No valid tool call found..."`

### Result Reporting
- Per-test: prompt, expected, got, attempts, ok
- Summary: passed/total, percentage

---

## References

- `evals/agent_eval.py` - Existing eval harness
- `evals/parser.py` - Multi-strategy parser
- `evals/tools.py` - Tool schemas
- `evals/config.py` - Configuration
- `evals/scenarios.json` - Test cases
- `src/tunacode/core/agents/agent_components/node_processor.py` - Real tool handling
- `src/tunacode/tools/decorators.py` - Tool decorators
