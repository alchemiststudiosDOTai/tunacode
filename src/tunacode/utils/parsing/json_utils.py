"""
Module: tunacode.utils.json_utils

JSON parsing utilities with enhanced error handling and concatenated object support.
"""

import json
from typing import Any

from tunacode.constants import READ_ONLY_TOOLS


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

    # Check if tool is read-only (safer to execute multiple times)
    if tool_name and tool_name in READ_ONLY_TOOLS:
        return True

    # For write/execute tools, multiple objects are potentially dangerous
    if tool_name is None:
        return False

    raise ConcatenatedJSONError(
        f"Multiple JSON objects not safe for tool {tool_name}",
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

        # Validate safety - fail loud if multiple objects would be discarded
        if not validate_tool_args_safety(objects, tool_name):
            if len(objects) > 1:
                raise ConcatenatedJSONError(
                    "Multiple JSON objects detected but tool safety unknown",
                    objects_found=len(objects),
                    tool_name=tool_name,
                ) from None
            return objects[0]

        if len(objects) == 1:
            return objects[0]

        return objects

    if not isinstance(result, dict):
        raise json.JSONDecodeError(f"Expected dict, got {type(result)}", json_string, 0)

    return result


def merge_json_objects(objects: list[dict[str, Any]], strategy: str = "first") -> dict[str, Any]:
    """
    Merge multiple JSON objects using different strategies.

    Args:
        objects: List of JSON objects to merge
        strategy: Merge strategy ("first", "last", "combine")

    Returns:
        Single merged JSON object
    """
    if not objects:
        return {}

    if len(objects) == 1:
        return objects[0]

    if strategy == "first":
        return objects[0]
    if strategy == "last":
        return objects[-1]
    if strategy == "combine":
        result: dict[str, Any] = {}
        for obj in objects:
            result.update(obj)
        return result

    raise ValueError(f"Unknown merge strategy: {strategy}")
