"""Unified tool registry for TunaCode tools.

This module defines a single source of truth for tool metadata and
provides a registry for discovery and documentation generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

if TYPE_CHECKING:  # Avoid runtime imports to prevent circular dependencies
    from .base import BaseTool


class ToolCategory(Enum):
    """Categories used for parallelization and policy rules."""

    READ_ONLY = "read_only"  # Parallel-safe tools (Read, Grep, LS, Glob)
    WRITE = "write"  # File modification tools (Write, Edit, MultiEdit)
    EXECUTE = "execute"  # System execution (Bash, RunCommand)
    TASK_MGMT = "task_mgmt"  # Task management (TodoWrite)
    PLANNING = "planning"  # Planning mode tools (ExitPlanMode)


@dataclass
class ToolDefinition:
    name: str
    category: ToolCategory
    description: str
    parameters: Dict[str, Any]
    # Optional metadata used by docs/examples
    example_args: Optional[Dict[str, Any]] = None
    brief: Optional[str] = None
    examples: Optional[List[tuple[str, str]]] = None
    # Optional reference to the implementing class
    tool_class: Optional[Type["BaseTool"]] = None


class ToolRegistry:
    """Simple in-memory registry for tool definitions."""

    _tools: Dict[str, ToolDefinition] = {}

    @classmethod
    def register(cls, definition: ToolDefinition) -> None:
        """Register or update a tool definition."""
        if not isinstance(definition.category, ToolCategory):
            raise TypeError("definition.category must be a ToolCategory")
        cls._tools[definition.name] = definition

    @classmethod
    def get(cls, name: str) -> Optional[ToolDefinition]:
        return cls._tools.get(name)

    @classmethod
    def get_all(cls) -> List[ToolDefinition]:
        return list(cls._tools.values())

    @classmethod
    def get_by_category(cls, category: ToolCategory) -> List[ToolDefinition]:
        return [t for t in cls._tools.values() if t.category is category]

    @classmethod
    def clear(cls) -> None:
        """Clear the registry (intended for tests)."""
        cls._tools.clear()
