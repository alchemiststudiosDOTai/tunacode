"""
Module: tunacode.utils.json_utils

JSON parsing utilities with enhanced error handling and concatenated object support.
"""

import json
from typing import Any


class ConcatenatedJSONError(Exception):
    """Raised when concatenated JSON objects are detected but cannot be safely handled."""

    def __init__(self, message: str, objects_found: int, tool_name: str | None = None):
        self.message = message
        self.objects_found = objects_found
        self.tool_name = tool_name
        super().__init__(message)


def split_concatenated_json(json_string: str) -> list[dict[str, Any]]:
    """
    Split concatenated JSON objects like {"a": 1}{"b": 2} into separate objects.

    Args:
        json_string: String containing potentially concatenated JSON objects

    Returns:
        List of parsed JSON objects

    Raises:
        json.JSONDecodeError: If no valid JSON objects can be extracted
    """
    objects = []
    brace_count = 0
    start_pos = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(json_string):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            if brace_count == 0:
                start_pos = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                potential_json = json_string[start_pos : i + 1].strip()
                try:
                    parsed = json.loads(potential_json)
                except json.JSONDecodeError:
                    continue

                if isinstance(parsed, dict):
                    objects.append(parsed)

    if not objects:
        raise json.JSONDecodeError("No valid JSON objects found", json_string, 0)

    return objects


def validate_tool_args_safety(objects: list[dict[str, Any]], tool_name: str | None = None) -> bool:
    """
    Validate whether it's safe to execute multiple JSON objects for a given tool.

    Args:
        objects: List of JSON objects to validate
        tool_name: Name of the tool (if known)

    Returns:
        bool: True if safe to execute, False otherwise

    Raises:
        ConcatenatedJSONError: If multiple objects detected for unsafe tool
    """
    if len(objects) <= 1:
        return True

    tool_label = tool_name or "<unknown>"
    raise ConcatenatedJSONError(
        f"Multiple JSON objects not supported for tool {tool_label}",
        objects_found=len(objects),
        tool_name=tool_name,
    )


def safe_json_parse(
    json_string: str, tool_name: str | None = None, allow_concatenated: bool = False
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Safely parse JSON with optional concatenated object support.

    Args:
        json_string: JSON string to parse
        tool_name: Name of the tool (for safety validation)
        allow_concatenated: Whether to attempt splitting concatenated objects

    Returns:
        Single dict if one object, or list of dicts if multiple objects

    Raises:
        json.JSONDecodeError: If parsing fails
        ConcatenatedJSONError: If concatenated objects are unsafe
    """
    try:
        # First, try normal JSON parsing
        result = json.loads(json_string)
    except json.JSONDecodeError as e:
        if not allow_concatenated or "Extra data" not in str(e):
            raise

        # Try to split concatenated objects
        objects = split_concatenated_json(json_string)

        # Validate safety - fail loud if multiple objects are found
        validate_tool_args_safety(objects, tool_name)

        if len(objects) == 1:
            return objects[0]

        return objects

    if not isinstance(result, dict):
        raise json.JSONDecodeError(f"Expected dict, got {type(result)}", json_string, 0)

    return result
