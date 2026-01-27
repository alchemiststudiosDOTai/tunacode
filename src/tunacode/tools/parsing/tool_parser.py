"""
Module: tunacode.tools.parsing.tool_parser

Multi-strategy fallback parser for extracting tool calls from text responses.
Handles non-standard tool calling formats from models like Qwen2.5-Coder.

Supported formats:
- Qwen2-style XML: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
- Hermes-style: <function=name>{...}</function>
- Code fences: ```json {"name": "...", ...} ```
- Raw JSON: {"name": "...", "arguments": {...}}
"""

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tunacode.tools.parsing.json_utils import split_concatenated_json


@dataclass(frozen=True, slots=True)
class ParsedToolCall:
    """Immutable representation of a parsed tool call.

    Attributes:
        tool_name: Name of the tool to call
        args: Arguments dictionary for the tool
        tool_call_id: Unique identifier for this tool call
    """

    tool_name: str
    args: dict[str, Any]
    tool_call_id: str


@dataclass
class ParseDiagnostics:
    """Diagnostic information about tool call parsing attempts.

    Attributes:
        text_preview: First 200 chars of input text
        text_length: Total length of input text
        detected_indicators: Which tool call indicators were found
        strategies_tried: List of (strategy_name, failure_reason) tuples
        success: Whether any strategy succeeded
        success_strategy: Name of successful strategy (if any)
    """

    text_preview: str = ""
    text_length: int = 0
    detected_indicators: list[str] = field(default_factory=list)
    strategies_tried: list[tuple[str, str]] = field(default_factory=list)
    success: bool = False
    success_strategy: str | None = None

    def format_for_debug(self) -> str:
        """Format diagnostics for debug output."""
        lines = [
            f"[TOOL_PARSE] text_len={self.text_length} preview={repr(self.text_preview[:100])}",
            f"[TOOL_PARSE] indicators_found={self.detected_indicators}",
        ]
        for strategy, reason in self.strategies_tried:
            lines.append(f"[TOOL_PARSE] strategy={strategy} result={reason}")
        if self.success:
            lines.append(f"[TOOL_PARSE] SUCCESS via {self.success_strategy}")
        else:
            lines.append("[TOOL_PARSE] FAILED: no strategy matched")
        return "\n".join(lines)


def _generate_tool_call_id() -> str:
    """Generate a unique tool call ID consistent with pydantic_ai format."""
    return str(uuid.uuid4())


QWEN2_PATTERN = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def parse_qwen2_xml(text: str) -> list[ParsedToolCall] | None:
    """Parse Qwen2-style XML tool calls.

    Format: <tool_call>{"name": "read_file", "arguments": {"filepath": "..."}}</tool_call>

    Args:
        text: Raw text potentially containing tool calls

    Returns:
        List of ParsedToolCall if matches found, None otherwise
    """
    matches = QWEN2_PATTERN.findall(text)
    if not matches:
        return None

    results: list[ParsedToolCall] = []
    for json_str in matches:
        parsed = _parse_tool_json(json_str)
        if parsed:
            results.append(parsed)

    return results if results else None


HERMES_PATTERN = re.compile(r"<function=(\w+)>\s*(\{.*?\})\s*</function>", re.DOTALL)


def parse_hermes_style(text: str) -> list[ParsedToolCall] | None:
    """Parse Hermes-style function call format.

    Format: <function=read_file>{"filepath": "/path/to/file"}</function>

    Args:
        text: Raw text potentially containing tool calls

    Returns:
        List of ParsedToolCall if matches found, None otherwise
    """
    matches = HERMES_PATTERN.findall(text)
    if not matches:
        return None

    results: list[ParsedToolCall] = []
    for tool_name, args_json in matches:
        try:
            args = json.loads(args_json)
            if isinstance(args, dict):
                results.append(
                    ParsedToolCall(
                        tool_name=tool_name,
                        args=args,
                        tool_call_id=_generate_tool_call_id(),
                    )
                )
        except json.JSONDecodeError:
            continue

    return results if results else None


CODE_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_code_fence(text: str) -> list[ParsedToolCall] | None:
    """Parse JSON tool calls inside code fences.

    Format: ```json {"name": "read_file", "arguments": {...}} ```

    Args:
        text: Raw text potentially containing tool calls

    Returns:
        List of ParsedToolCall if matches found, None otherwise
    """
    matches = CODE_FENCE_PATTERN.findall(text)
    if not matches:
        return None

    results: list[ParsedToolCall] = []
    for json_str in matches:
        parsed = _parse_tool_json(json_str)
        if parsed:
            results.append(parsed)

    return results if results else None


def parse_raw_json(text: str) -> list[ParsedToolCall] | None:
    """Parse raw JSON tool calls embedded in text.

    Formats supported:
    - {"name": "tool_name", "arguments": {...}}
    - {"tool": "tool_name", "args": {...}}

    Args:
        text: Raw text potentially containing tool calls

    Returns:
        List of ParsedToolCall if matches found, None otherwise
    """
    try:
        objects = split_concatenated_json(text)
    except (json.JSONDecodeError, ValueError):
        return None

    results: list[ParsedToolCall] = []
    for obj in objects:
        parsed = _normalize_tool_object(obj)
        if parsed:
            results.append(parsed)

    return results if results else None


def _parse_tool_json(json_str: str) -> ParsedToolCall | None:
    """Parse a JSON string into a ParsedToolCall.

    Handles both {"name": ..., "arguments": ...} and {"tool": ..., "args": ...} formats.
    """
    try:
        obj = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    return _normalize_tool_object(obj)


def _normalize_tool_object(obj: object) -> ParsedToolCall | None:
    """Normalize various tool call object formats into ParsedToolCall.

    Supported formats:
    - {"name": "...", "arguments": {...}}
    - {"tool": "...", "args": {...}}
    - {"function": "...", "parameters": {...}}
    """
    if not isinstance(obj, dict):
        return None

    # Extract tool name
    tool_name = obj.get("name") or obj.get("tool") or obj.get("function")
    if not tool_name or not isinstance(tool_name, str):
        return None

    # Extract arguments
    args = obj.get("arguments") or obj.get("args") or obj.get("parameters") or {}
    if not isinstance(args, dict):
        # Try to parse if string
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        else:
            args = {}

    return ParsedToolCall(
        tool_name=tool_name,
        args=args,
        tool_call_id=_generate_tool_call_id(),
    )


PARSING_STRATEGIES: list[tuple[str, Callable[[str], list[ParsedToolCall] | None]]] = [
    ("qwen2_xml", parse_qwen2_xml),
    ("hermes_style", parse_hermes_style),
    ("code_fence", parse_code_fence),
    ("raw_json", parse_raw_json),
]

# Indicators used to detect potential tool calls
TOOL_CALL_INDICATORS = [
    "<tool_call>",
    "</tool_call>",
    "<function=",
    "</function>",
    "</arg_value>",  # Non-standard format some models use
    '"name":',
    '"tool":',
    "```json",
]


def parse_tool_calls_from_text(
    text: str, *, collect_diagnostics: bool = False
) -> list[ParsedToolCall] | tuple[list[ParsedToolCall], ParseDiagnostics]:
    """Parse tool calls from text using multi-strategy fallback.

    Tries each parsing strategy in order until one succeeds.
    Strategies are ordered from most specific to most general.

    Args:
        text: Raw text potentially containing embedded tool calls
        collect_diagnostics: If True, return (results, diagnostics) tuple

    Returns:
        List of ParsedToolCall objects. Empty list if no tool calls found.
        If collect_diagnostics=True, returns (results, ParseDiagnostics).

    Note:
        Does NOT raise on failure - returns empty list per fail-fast-but-graceful design.
        The caller should decide how to handle empty results.
    """
    diagnostics = ParseDiagnostics() if collect_diagnostics else None

    if not text or not text.strip():
        if diagnostics:
            diagnostics.text_length = 0
            diagnostics.text_preview = ""
            diagnostics.strategies_tried.append(("pre-check", "empty_text"))
            return [], diagnostics
        return []

    if diagnostics:
        diagnostics.text_length = len(text)
        diagnostics.text_preview = text[:200]
        # Check which indicators are present
        text_lower = text.lower()
        for ind in TOOL_CALL_INDICATORS:
            if ind.lower() in text_lower:
                diagnostics.detected_indicators.append(ind)

    for strategy_name, strategy_func in PARSING_STRATEGIES:
        try:
            result = strategy_func(text)
            if result:
                if diagnostics:
                    diagnostics.strategies_tried.append(
                        (strategy_name, f"matched {len(result)} calls")
                    )
                    diagnostics.success = True
                    diagnostics.success_strategy = strategy_name
                    return result, diagnostics
                return result
            if diagnostics:
                diagnostics.strategies_tried.append((strategy_name, "no_match"))
        except Exception as e:
            if diagnostics:
                diagnostics.strategies_tried.append((strategy_name, f"error: {e}"))

    if diagnostics:
        return [], diagnostics
    return []


def has_potential_tool_call(text: str) -> bool:
    """Quick check if text might contain a tool call.

    This is a fast pre-filter before expensive parsing.

    Args:
        text: Text to check

    Returns:
        True if text appears to contain tool call patterns
    """
    if not text:
        return False

    # Quick pattern indicators
    indicators = [
        "<tool_call>",
        "<function=",
        '"name":',
        '"tool":',
        "```json",
    ]

    text_lower = text.lower()
    return any(ind.lower() in text_lower for ind in indicators)
