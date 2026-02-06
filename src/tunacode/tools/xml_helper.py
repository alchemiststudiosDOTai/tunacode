"""Helper module for loading prompts and schemas from XML files."""

from pathlib import Path

from defusedxml.ElementTree import ParseError
from defusedxml.ElementTree import parse as xml_parse

from tunacode.infrastructure.cache.manager import CACHE_XML_PROMPTS, get_cache_manager


def load_prompt_from_xml(tool_name: str) -> str | None:
    """Load and return the base prompt from XML file.

    Args:
        tool_name: Name of the tool (e.g., 'grep', 'glob')

    Returns:
        str: The loaded prompt from XML or None if not found
    """
    cache = get_cache_manager().get_cache(CACHE_XML_PROMPTS)

    if tool_name in cache:
        return cache[tool_name]

    prompt_file = Path(__file__).parent / "prompts" / f"{tool_name}_prompt.xml"
    if not prompt_file.exists():
        cache[tool_name] = None
        return None

    try:
        tree = xml_parse(prompt_file)
    except ParseError:
        cache[tool_name] = None
        return None

    root = tree.getroot()
    description = root.find("description")
    if description is None or description.text is None:
        cache[tool_name] = None
        return None

    result = description.text.strip()
    cache[tool_name] = result
    return result
