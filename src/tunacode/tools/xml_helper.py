"""Helper module for loading prompts and schemas from XML files."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import defusedxml.ElementTree as ET

logger = logging.getLogger(__name__)


@lru_cache(maxsize=32)
def load_prompt_from_xml(tool_name: str) -> str | None:
    """Load and return the base prompt from XML file.

    Args:
        tool_name: Name of the tool (e.g., 'grep', 'glob')

    Returns:
        str: The loaded prompt from XML or None if not found
    """
    try:
        prompt_file = Path(__file__).parent / "prompts" / f"{tool_name}_prompt.xml"
        if prompt_file.exists():
            tree = ET.parse(prompt_file)
            root = tree.getroot()
            description = root.find("description")
            if description is not None:
                return description.text.strip()
    except Exception as e:
        logger.warning(f"Failed to load XML prompt for {tool_name}: {e}")
    return None


@lru_cache(maxsize=32)
def load_parameters_schema_from_xml(tool_name: str) -> dict[str, Any] | None:
    """Load and return the parameters schema from XML file.

    Args:
        tool_name: Name of the tool (e.g., 'grep', 'glob')

    Returns:
        Dict containing the JSON schema for tool parameters or None if not found
    """
    try:
        prompt_file = Path(__file__).parent / "prompts" / f"{tool_name}_prompt.xml"
        if prompt_file.exists():
            tree = ET.parse(prompt_file)
            root = tree.getroot()
            parameters = root.find("parameters")
            if parameters is not None:
                schema: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
                required_fields: list[str] = []

                for param in parameters.findall("parameter"):
                    name = param.get("name")
                    required = param.get("required", "false").lower() == "true"
                    param_type = param.find("type")
                    description = param.find("description")

                    if name and param_type is not None:
                        prop = {
                            "type": param_type.text.strip(),
                            "description": description.text.strip()
                            if description is not None
                            else "",
                        }

                        # Add enum values if present
                        enums = param.findall("enum")
                        if enums:
                            prop["enum"] = [e.text.strip() for e in enums]

                        schema["properties"][name] = prop
                        if required:
                            required_fields.append(name)

                schema["required"] = required_fields
                return schema
    except Exception as e:
        logger.warning(f"Failed to load parameters from XML for {tool_name}: {e}")
    return None
