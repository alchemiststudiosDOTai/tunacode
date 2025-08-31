"""Tool definition decorator for unified tool registration.

This module provides the @tool_definition decorator that allows tools to be
defined once and automatically generate all necessary metadata.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from .registry import ToolCategory, ToolDefinition, ToolRegistry

if TYPE_CHECKING:
    from .base import BaseTool


def tool_definition(
    name: str,
    category: ToolCategory,
    description: str,
    parameters: Dict[str, Any],
    example_args: Optional[Dict[str, Any]] = None,
    brief: Optional[str] = None,
    examples: Optional[List[tuple[str, str]]] = None,
):
    """Decorator to register a tool with unified metadata.

    Args:
        name: Tool name (e.g., "grep", "Read")
        category: Tool category for parallelization rules
        description: Tool description for prompts
        parameters: JSON schema for tool parameters
        example_args: Example arguments for documentation
        brief: Brief description for tool listings
        examples: List of (description, example) tuples

    Returns:
        Decorated class with registered metadata
    """

    def decorator(cls: Type["BaseTool"]) -> Type["BaseTool"]:
        # Create and register the tool definition
        definition = ToolDefinition(
            name=name,
            category=category,
            description=description,
            parameters=parameters,
            example_args=example_args,
            brief=brief,
            examples=examples,
            tool_class=cls,
        )

        ToolRegistry.register(definition)

        # Store definition on the class for easy access
        setattr(cls, "_tool_definition", definition)

        return cls

    return decorator
