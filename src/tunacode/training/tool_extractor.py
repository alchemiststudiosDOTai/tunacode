"""Extract tunacode tool definitions into JSON Schema format for training data.

This module extracts function signatures from tunacode tools and converts
them into ToolDefinition objects that can be used to generate training data.
"""

import inspect
import json
import types
from collections.abc import Callable
from typing import Any, Union, get_args, get_origin, get_type_hints

from tunacode.training.schema import ToolDefinition, ToolParameter


def _python_type_to_json_schema(py_type: Any) -> str:
    """Convert Python type annotation to JSON Schema type string."""
    origin = get_origin(py_type)

    # Handle None type directly
    if py_type is type(None):
        return "null"

    # Handle UnionType (X | Y) from Python 3.10+
    if isinstance(py_type, types.UnionType):
        args = get_args(py_type)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _python_type_to_json_schema(non_none_args[0])
        return "string"  # Fallback for complex unions

    # Handle typing.Union
    if origin is Union:
        args = get_args(py_type)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _python_type_to_json_schema(non_none_args[0])
        return "string"  # Fallback for complex unions

    # Handle list types
    if origin is list:
        return "array"

    # Handle dict types
    if origin is dict:
        return "object"

    # Handle basic types
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }

    if py_type in type_map:
        return type_map[py_type]

    # Fallback: try to get the name
    if hasattr(py_type, "__name__"):
        name = py_type.__name__.lower()
        if name in ("str", "string"):
            return "string"
        if name in ("int", "integer"):
            return "integer"
        if name in ("float", "number"):
            return "number"
        if name in ("bool", "boolean"):
            return "boolean"

    return "string"  # Default fallback


def _get_parameter_default(param: inspect.Parameter) -> Any:
    """Get the default value for a parameter, or None if no default."""
    if param.default is inspect.Parameter.empty:
        return None
    return param.default


def _is_required(param: inspect.Parameter) -> bool:
    """Determine if a parameter is required."""
    return param.default is inspect.Parameter.empty


def _extract_param_description(doc: str | None, param_name: str) -> str:
    """Extract parameter description from docstring.

    Looks for patterns like:
        param_name: Description here.
    """
    if not doc:
        return f"The {param_name} parameter."

    lines = doc.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match "param_name:" or "param_name :" at start of line
        if stripped.startswith(f"{param_name}:") or stripped.startswith(f"{param_name} :"):
            # Get the description after the colon
            _, _, desc = stripped.partition(":")
            desc = desc.strip()
            # Check if description continues on next lines (indented)
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                if next_line.strip() and not next_line.strip()[0].isalpha():
                    break
                if next_line.startswith("        ") or next_line.startswith("\t\t"):
                    desc += " " + next_line.strip()
                else:
                    break
            return desc if desc else f"The {param_name} parameter."

    return f"The {param_name} parameter."


def extract_tool_definition(func: Callable[..., Any]) -> ToolDefinition:
    """Extract a ToolDefinition from a Python function.

    Args:
        func: The function to extract the tool definition from.

    Returns:
        A ToolDefinition object containing the tool's name, description, and parameters.
    """
    # Get function name
    name = func.__name__

    # Get description from docstring
    doc = inspect.getdoc(func) or ""
    # First line of docstring is the description
    description = doc.split("\n")[0] if doc else f"The {name} tool."

    # Get type hints and signature
    try:
        type_hints = get_type_hints(func)
    except Exception:
        type_hints = {}

    sig = inspect.signature(func)

    parameters: list[ToolParameter] = []

    for param_name, param in sig.parameters.items():
        # Skip self, cls, and *args, **kwargs
        if param_name in ("self", "cls"):
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        # Get type annotation
        py_type = type_hints.get(param_name, str)
        json_type = _python_type_to_json_schema(py_type)

        # Get description from docstring
        param_desc = _extract_param_description(doc, param_name)

        # Get default value
        default = _get_parameter_default(param)

        # Determine if required
        required = _is_required(param)

        parameters.append(
            ToolParameter(
                name=param_name,
                type=json_type,
                description=param_desc,
                required=required,
                default=default,
            )
        )

    return ToolDefinition(
        name=name,
        description=description,
        parameters=parameters,
    )


def get_tunacode_tool_registry() -> list[ToolDefinition]:
    """Get all tunacode tool definitions as a registry.

    Returns:
        List of ToolDefinition objects for all core tunacode tools.
    """
    # Import all tools
    from tunacode.tools.bash import bash
    from tunacode.tools.glob import glob
    from tunacode.tools.grep import grep
    from tunacode.tools.list_dir import list_dir
    from tunacode.tools.read_file import read_file
    from tunacode.tools.update_file import update_file
    from tunacode.tools.web_fetch import web_fetch
    from tunacode.tools.write_file import write_file

    tools = [
        bash,
        glob,
        grep,
        list_dir,
        read_file,
        update_file,
        web_fetch,
        write_file,
    ]

    return [extract_tool_definition(tool) for tool in tools]


def get_tools_json_schema() -> str:
    """Get all tool definitions as a JSON Schema string.

    Returns:
        JSON string containing all tool definitions in OpenAI-compatible format.
    """
    registry = get_tunacode_tool_registry()
    schemas = [tool.to_json_schema() for tool in registry]
    return json.dumps(schemas, indent=2)


def get_tools_for_training() -> str:
    """Get tool definitions formatted for training data.

    Returns:
        JSON string of tool definitions for the "tools" field in ShareGPT format.
    """
    return get_tools_json_schema()
