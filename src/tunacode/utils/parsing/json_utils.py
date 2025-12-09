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


def split_concatenated_json(json_string: str, strict_mode: bool = True) -> list[dict[str, Any]]:
    """
    Split concatenated JSON objects like {"a": 1}{"b": 2} into separate objects.

    Args:
        json_string: String containing potentially concatenated JSON objects
        strict_mode: If True, only returns valid JSON objects. If False, attempts
                    to recover partial objects.

    Returns:
        List of parsed JSON objects

    Raises:
        json.JSONDecodeError: If no valid JSON objects can be extracted
        ConcatenatedJSONError: If multiple objects found but not safe to process
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
                    if isinstance(parsed, dict):
                        objects.append(parsed)
                    else:
                        pass
                except json.JSONDecodeError:
                    if strict_mode:
                        pass
                    else:
                        pass
                    continue

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
    if tool_name:
        pass
        raise ConcatenatedJSONError(
            f"Multiple JSON objects not safe for tool {tool_name}",
            objects_found=len(objects),
            tool_name=tool_name,
        )
    else:
        return False


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
        if isinstance(result, dict):
            return result
        else:
            raise json.JSONDecodeError(f"Expected dict, got {type(result)}", json_string, 0)

    except json.JSONDecodeError as e:
        if not allow_concatenated or "Extra data" not in str(e):
            raise

        # Try to split concatenated objects
        objects = split_concatenated_json(json_string)

        # Validate safety
        if validate_tool_args_safety(objects, tool_name):
            if len(objects) == 1:
                return objects[0]
            else:
                return objects
        else:
            # Not safe - return first object
            return objects[0]


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
    elif strategy == "last":
        return objects[-1]
    elif strategy == "combine":
        # Combine all objects, later values override earlier ones
        result = {}
        for obj in objects:
            result.update(obj)
        return result
    else:
        raise ValueError(f"Unknown merge strategy: {strategy}")
