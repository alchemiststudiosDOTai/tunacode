# Qwen2-Style Tool Calling Pattern

## Problem

Qwen2.5-Coder models use **Qwen2-style function calling** (XML-based), NOT Hermes-style (structured `tool_calls`).

When served via vLLM:
- vLLM expects Hermes-style and returns empty `tool_calls` array
- Model outputs tool intent as **raw text** with JSON or `<tool_call>` XML tags
- `finish_reason` is `"stop"` instead of `"tool_calls"`

## How It Manifests

```python
# vLLM response for Qwen2.5-Coder
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": '{"name": "read_file", "arguments": {"path": "src/main.py"}}',
      "tool_calls": []  # EMPTY - model doesn't populate this
    },
    "finish_reason": "stop"  # NOT "tool_calls"
  }]
}
```

pydantic_ai converts this to:
- `TextPart` with content containing the JSON (tool call is lost)
- No `ToolCallPart` objects

## Output Formats to Parse

Qwen2.5-Coder may output tool calls in several text formats:

```
# Format 1: Raw JSON
{"name": "read_file", "arguments": {"path": "src/main.py"}}

# Format 2: XML tags (Qwen2-style)
<tool_call>
{"name": "read_file", "arguments": {"path": "src/main.py"}}
</tool_call>

# Format 3: With surrounding text/garbage
拓
{"name": "read_file", "arguments": {"path": "src/main.py"}}
สมาร์ทโฟน

# Format 4: Code fences
```json
{"name": "read_file", "arguments": {"path": "src/main.py"}}
```
```

## Real Parser Code

### Location: `tunacode-finetuning/src/tunacode_training/eval/parser.py`

```python
"""Parse tool calls from model output in various formats."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedToolCall:
    """Represents an extracted tool call from model output."""

    name: str | None
    arguments: dict[str, Any]
    raw_text: str
    parse_success: bool
    parse_method: str  # Which extraction method succeeded


def extract_tool_call(text: str) -> ParsedToolCall:
    """
    Extract function call from model output.

    Tries multiple extraction strategies in order:
    1. <tool_call>JSON</tool_call> tags (training format)
    2. Direct JSON object with name/arguments
    3. ```json code blocks
    4. Loose JSON matching
    5. Fallback regex for tool name only

    Args:
        text: Raw model output text

    Returns:
        ParsedToolCall with extracted data or empty on failure
    """
    # Strategy 1: <tool_call> tags (our training format)
    result = _extract_from_tool_tags(text)
    if result:
        return ParsedToolCall(
            name=result.get("name"),
            arguments=normalize_arguments(result.get("arguments", {})),
            raw_text=text,
            parse_success=True,
            parse_method="tool_tags",
        )

    # Strategy 2: Direct JSON object
    result = _extract_direct_json(text)
    if result:
        return ParsedToolCall(
            name=result.get("name"),
            arguments=normalize_arguments(result.get("arguments", {})),
            raw_text=text,
            parse_success=True,
            parse_method="direct_json",
        )

    # Strategy 3: ```json code blocks
    result = _extract_from_json_block(text)
    if result:
        return ParsedToolCall(
            name=result.get("name"),
            arguments=normalize_arguments(result.get("arguments", {})),
            raw_text=text,
            parse_success=True,
            parse_method="json_block",
        )

    # Strategy 4: Loose JSON - find any JSON object with "name"
    result = _extract_loose_json(text)
    if result:
        return ParsedToolCall(
            name=result.get("name"),
            arguments=normalize_arguments(result.get("arguments", {})),
            raw_text=text,
            parse_success=True,
            parse_method="loose_json",
        )

    # Strategy 5: Fallback - just find the tool name
    name = _extract_name_only(text)
    if name:
        return ParsedToolCall(
            name=name,
            arguments={},
            raw_text=text,
            parse_success=True,
            parse_method="name_only",
        )

    # Complete failure
    return ParsedToolCall(
        name=None,
        arguments={},
        raw_text=text,
        parse_success=False,
        parse_method="none",
    )


def _extract_from_tool_tags(text: str) -> dict | None:
    """Extract JSON from <tool_call>...</tool_call> tags."""
    pattern = r"<tool_call>\s*(.*?)\s*</tool_call>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and "name" in data:
                return data
        except json.JSONDecodeError:
            pass
    return None


def _extract_from_json_block(text: str) -> dict | None:
    """Extract from ```json ... ``` code blocks."""
    pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and "name" in data:
                return data
        except json.JSONDecodeError:
            pass
    return None


def _extract_direct_json(text: str) -> dict | None:
    """Extract direct JSON object with name and arguments."""
    # Look for balanced braces containing "name"
    # Start from each { and try to parse
    for i, char in enumerate(text):
        if char == "{":
            # Try to find matching closing brace
            depth = 1
            j = i + 1
            while j < len(text) and depth > 0:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                j += 1

            if depth == 0:
                candidate = text[i:j]
                try:
                    data = json.loads(candidate)
                    if isinstance(data, dict) and "name" in data:
                        return data
                except json.JSONDecodeError:
                    pass
    return None


def _extract_loose_json(text: str) -> dict | None:
    """Try to extract JSON even with some formatting issues."""
    # Look for patterns like {"name": "tool_name", "arguments": {...}}
    pattern = r'\{\s*"name"\s*:\s*"([^"]+)"[^}]*(?:"arguments"\s*:\s*(\{[^}]*\}))?[^}]*\}'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        name = match.group(1)
        args_str = match.group(2)
        arguments = {}
        if args_str:
            try:
                arguments = json.loads(args_str)
            except json.JSONDecodeError:
                pass
        return {"name": name, "arguments": arguments}
    return None


def _extract_name_only(text: str) -> str | None:
    """Last resort: just find the tool name."""
    # Look for "name": "tool_name" pattern
    pattern = r'"name"\s*:\s*"([^"]+)"'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None


def normalize_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize argument values for comparison.

    - Strip whitespace from strings
    - Normalize paths (remove trailing slashes, handle ./)
    - Keep other types as-is
    """
    normalized = {}
    for key, value in args.items():
        if isinstance(value, str):
            normalized[key] = _normalize_string_value(value)
        else:
            normalized[key] = value
    return normalized


def _normalize_string_value(value: str) -> str:
    """Normalize a string value."""
    # Strip whitespace
    value = value.strip()

    # Normalize paths
    # Remove trailing slashes (but not the root /)
    if len(value) > 1 and value.endswith("/"):
        value = value.rstrip("/")

    # Remove leading ./ for relative paths
    if value.startswith("./"):
        value = value[2:]

    return value
```

### Location: `mini_evals/parser.py` (wrapper with OpenAI tool_calls support)

```python
"""Parse tool calls from model output with Qwen-compatible fallbacks."""

import json
import re
from dataclasses import dataclass
from typing import Any

from tunacode_training.eval.parser import extract_tool_call as _fallback_extract

TOOL_XML_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
TOOL_JSON_RE = re.compile(r'\{"name":\s*"([^"]+)",\s*"arguments":\s*(\{[^}]*\})\}')
PATH_KEYS = ("directory", "filepath")


class ToolParseError(ValueError):
    """Raised when tool call parsing fails."""
    pass


def _parse_json(text: str, label: str) -> dict:
    """Parse JSON with error context."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolParseError(f"invalid {label} JSON") from exc
    if not isinstance(data, dict):
        raise ToolParseError(f"{label} JSON must be an object")
    return data


def _validate_tool_call(tool_name: str | None, args: object, allowed: set[str]) -> tuple[str | None, dict | None]:
    """Validate tool name and arguments."""
    if not tool_name:
        return None, None
    if tool_name not in allowed:
        raise ToolParseError(f"unknown tool: {tool_name}")
    if not isinstance(args, dict):
        raise ToolParseError("tool args must be an object")
    return tool_name, args


def normalize(args: dict) -> dict:
    """Normalize path arguments by stripping trailing slashes."""
    return {k: v.rstrip("/") if isinstance(v, str) and k in PATH_KEYS else v for k, v in args.items()}


def parse_tool_call(msg, allowed_tools: set[str]) -> tuple[str | None, dict | None]:
    """
    Parse tool call from message using multiple strategies.

    Strategies (in order):
    1. OpenAI tool_calls object
    2. <tool_call> XML tags
    3. Raw JSON regex
    4. Fallback parser (code fences, loose JSON, etc.)
    """
    # Strategy 1: OpenAI tool_calls object
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        tc = tool_calls[0]
        args = tc.function.arguments
        if isinstance(args, str):
            args = _parse_json(args, "tool args")
        return _validate_tool_call(tc.function.name, args, allowed_tools)

    content = msg.content or ""
    if not content:
        return None, None

    # Strategy 2: <tool_call> XML tags
    if match := TOOL_XML_RE.search(content):
        data = _parse_json(match.group(1), "tool call")
        return _validate_tool_call(data.get("name"), data.get("arguments", {}), allowed_tools)

    # Strategy 3: Raw JSON regex
    if match := TOOL_JSON_RE.search(content):
        tool_args = _parse_json(match.group(2), "tool args")
        return _validate_tool_call(match.group(1), tool_args, allowed_tools)

    # Strategy 4: Fallback parser (handles code fences, loose JSON, etc.)
    result = _fallback_extract(content)
    if result.parse_success and result.name:
        return _validate_tool_call(result.name, result.arguments, allowed_tools)

    return None, None
```

## Workarounds (External)

1. Use **Ollama** instead of vLLM (supports Qwen2-style natively)
2. Use **Qwen-Agent** instead of vLLM
3. Use standard **Qwen2.5** (non-Coder) models with vLLM

## Reference

GitHub Issue: https://github.com/QwenLM/Qwen3-Coder/issues/180
