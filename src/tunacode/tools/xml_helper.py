"""Helper module for loading prompts and schemas from XML files."""

from functools import lru_cache
from pathlib import Path

import defusedxml.ElementTree as ET


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
        pass
    return None
