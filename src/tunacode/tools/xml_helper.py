"""Helper module for loading prompts and schemas from XML files."""

from functools import lru_cache
from pathlib import Path

from defusedxml.ElementTree import ParseError
from defusedxml.ElementTree import parse as xml_parse


@lru_cache(maxsize=32)
def load_prompt_from_xml(tool_name: str) -> str | None:
    """Load and return the base prompt from XML file.

    Args:
        tool_name: Name of the tool (e.g., 'grep', 'glob')

    Returns:
        str: The loaded prompt from XML or None if not found
    """
    prompt_file = Path(__file__).parent / "prompts" / f"{tool_name}_prompt.xml"
    if not prompt_file.exists():
        return None

    try:
        tree = xml_parse(prompt_file)
    except ParseError:
        return None

    root = tree.getroot()
    description = root.find("description")
    if description is None or description.text is None:
        return None

    return description.text.strip()
